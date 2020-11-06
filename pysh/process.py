__all__ = 'PIPE', 'Process', 'Result', 'ResultError'

from .fd import FD
from .pipe import InputPipe, OutputPipe
from sys import platform

if platform == 'win32':
    raise NotImplementedError('Windows is not currently supported')
else:
    from . import posix as backend

PIPE = -1


def get_input(stream):
    if stream is None or isinstance(stream, FD):
        return stream
    if isinstance(stream, int):
        return FD(stream, 'rb')
    if isinstance(stream, OutputPipe):
        return stream.read_fd
    if isinstance(stream, Process):
        return get_input(stream.stdout)
    if hasattr(stream, 'fileno'):
        return get_input(stream.fileno())
    try:
        data = memoryview(stream)
    except TypeError:
        pass
    else:
        return InputPipe(data)
    raise ValueError(f'not sure how to use {repr(stream)} of type {type(stream)}')


def get_output(stream):
    if stream is None:
        return None
    if stream == PIPE:
        return OutputPipe()
    if isinstance(stream, int):
        return FD(stream, 'wb')
    if hasattr(stream, 'fileno'):
        return get_output(stream.fileno())
    raise ValueError(f'not sure how to use {repr(stream)} of type {type(stream)}')


class Process:
    """spawns a process

    This is a bit like subprocess.Popen, but chaining processes works:

    >>> p = Process('tr a-z A-Z', b'x' * 12345678, stdout=PIPE)
    >>> q = Process('cat', p, stdout=PIPE)
    >>> len(q.wait().stdout)
    12345678
    """
    def __init__(
        self,
        argv, stdin=None, stdout=None, stderr=None,
        shell=False, env=None,
    ):
        """initialize the process
        argv:   arguments to process; will be run through shlex.split() if a str and shell=False
        stdin:  input data, generally an int or something with a .fileno() method
                if bytes-like, gets wrapped in an InputPipe
                if Process, its .stdout is used*
        stdout: standard output, generally an int or something with a .fileno() method
                if PIPE == -1, set to an OutputPipe
        stderr: standard error, generally an int or something with a .fileno() method
                if PIPE == -1, set to an OutputPipe
        shell:  whether to run in a shell
                if False-like, don't run in a shell
                if exactly True, run ['sh', '-c', 'argv']
                if str, run through shlex.split() and append '-c' if there's only one token
                otherwise, use as is

        *If stdin is a process, it is treated specially. In particular Process.waitall() will
        work its way back to it, making sure not to try reading its stdout.
        """
        from shlex import split
        self.argv = argv
        self.result = None

        if shell:
            if shell is True:
                shell = 'sh -c'
            if isinstance(shell, str):
                shell = split(shell)
                if len(shell) == 1:
                    shell.append('-c')
            shell.append(argv)
        elif isinstance(argv, str):
            argv = split(argv)

        self.input = stdin if isinstance(stdin, Process) else None
        self.streams = get_input(stdin), get_output(stdout), get_output(stderr)
        self.pid = backend.spawn(argv, env, *self.streams)

    @property
    def stdin(self):
        return self.streams[0]

    @property
    def stdout(self):
        return self.streams[1]

    @property
    def stderr(self):
        return self.streams[2]

    @property
    def outputs(self):
        return self.streams[1:]

    def waitpid(self):
        r"""like os.waitpid(), but returns an exit status

        NOTE: you should probably use process.wait().returncode instead

        >>> Process('exit 7').waitpid()
        7
        """
        return backend.wait(self.pid)

    def waitpid_all(self):
        r"""recursive version of waitpid()

        NOTE: you should probably use process.wait_all() instead

        >>> Process('exit 2', Process('exit 1')).waitpid_all()
        (1, 2)
        """
        status = self.waitpid()
        previous = () if self.input is None else self.input.waitpid_all()
        return previous + ( status, )

    def close_local(self):
        r"""close local ends of file descriptors

        This should happen after all processes have been started and before
        any attempt to read from their outputs.

        NOTE: you should probably use process.wait() or process.wait_all()

        >>> p = Process('echo AAA', stdout=PIPE)
        >>> p.close_local()
        >>> p.read()
        (b'AAA\n', None)
        >>> p.waitpid()
        0
        """
        for stream in self.outputs:
            if isinstance(stream, OutputPipe):
                stream.close_local()

    def read(self, stdout=True, stderr=True):
        r"""read outputs of process

        stdout, stderr: if False, skip reading that stream

        NOTE: you should probably use process.wait()

        >>> p = Process('echo AAA', stdout=PIPE)
        >>> p.close_local()
        >>> p.read()
        (b'AAA\n', None)
        >>> p.waitpid()
        0
        """
        try_read = stdout, stderr
        return tuple(
            stream.read() if read and stream is not None and stream.readable() else None
            for stream, read in zip(self.outputs, try_read)
        )

    def read_all(self, stdout=True, stderr=True):
        r"""recursive version of read()

        NOTE: you should probably use process.wait_all()

        >>> p = Process('tr a-z A-Z', Process('echo abc', None, PIPE), PIPE)
        >>> p.argv_all()
        ('echo abc', 'tr a-z A-Z')
        >>> p.read_all()
        ((None, None), (b'ABC\n', None))
        >>> p.waitpid_all()
        (0, 0)
        """
        self.close_local()

        previous = () if self.input is None else self.input.read_all(stdout=False, stderr=True)

        output = self.read(stdout, stderr)

        return previous + ( output, )

    def argv_all(self):
        r"""collect argvs from entire process chain

        NOTE: you should probably use process.wait_all()

        >>> p = Process('tr a-z A-Z', Process('echo abc', None, PIPE), PIPE)
        >>> p.argv_all()
        ('echo abc', 'tr a-z A-Z')
        >>> p.read_all()
        ((None, None), (b'ABC\n', None))
        >>> p.waitpid_all()
        (0, 0)
        """
        previous = () if self.input is None else self.input.argv_all()
        return previous + (self.argv,)

    def wait_all(self):
        r"""wait on every process of the chain and collect results

        >>> Process('tr a-z A-Z', Process('echo abc', None, PIPE), PIPE).wait_all()
        (Result(argv='echo abc', status=0), Result(argv='tr a-z A-Z', status=0, stdout=b'ABC\n'))
        """
        argvs = self.argv_all()
        outputs = self.read_all()
        statuses = self.waitpid_all()

        results = tuple(
            Result(argv, status, stdout, stderr)
            for argv, status, (stdout, stderr) in zip(argvs, statuses, outputs)
        )
        return results

    def wait(self):
        r"""short for process.wait_all()[-1]

        >>> Process('tr a-z A-Z', Process('echo abc', None, PIPE), PIPE).wait()
        Result(argv='tr a-z A-Z', status=0, stdout=b'ABC\n')
        """
        return self.wait_all()[-1]


class ResultBase:
    def __init__(self, argv, status, stdout=None, stderr=None):
        self.argv = argv
        self.status = status
        self.stdout = stdout
        self.stderr = stderr

    def __repr__(self):
        param_str = ', '.join(
            f'{n}={repr(a)}'
            for n, a in vars(self).items()
            if a is not None
        )
        return f'{type(self).__name__}({param_str})'

    def __str__(self):
        return repr(self)

    def __iter__(self):
        return iter(vars(self).values())


class Result(ResultBase):
    """the result after waiting on a process"""
    def check(self):
        """raise an error if status != 0"""
        if self.status != 0:
            raise ResultError(*self)
        return self

    def die(self):
        """exit with status if status != 0"""
        from sys import stderr, exit
        if self.status == 0:
            return self.check()
        if self.stderr is not None:
            stderr.write(self.stderr)
        exit(self.status)


class ResultError(ResultBase, Exception):
    """the result as an error, usually raised if a result.status != 0"""
