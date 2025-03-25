__all__ = 'PIPE', 'Process', 'Result', 'ResultError', 'change_default_backend'

from .fd import FD
from .pipe import InputPipe, OutputPipe
from .inspect import children
from sys import platform
import os
from signal import Signals, SIGKILL, SIGTERM

PIPE = -1


def get_signal(sig: Signals | int | str) -> Signals:
    if isinstance(sig, str):
        sig = sig.upper()
        return Signals[sig if sig.startswith('SIG') else f'SIG{sig}']
    return Signals(sig)


def get_backend(name=None):
    if name == 'subprocess':
        from . import subprocess as backend
        return backend
    if name == 'posix_spawn':
        from . import posix_spawn as backend
        return backend
    if name == 'fork_exec':
        from . import fork_exec as backend
        return backend
    if name == 'default':
        return get_backend.default
    raise ValueError(f'unknown backend: {name}')


if 'PYSH_BACKEND' in os.environ:
    get_backend.default = get_backend(os.environ['PYSH_BACKEND'])
elif platform == 'win32':
    get_backend.default = get_backend('subprocess')
elif hasattr(os, 'posix_spawnp'):
    get_backend.default = get_backend('posix_spawn')
else:
    get_backend.default = get_backend('fork_exec')


def change_default_backend(name_or_namespace):
    if isinstance(name_or_namespace, str):
        get_backend.default = get_backend(name_or_namespace)
    else:
        name_or_namespace.spawn
        name_or_namespace.wait
        get_backend.default = name_or_namespace
    return get_backend.default


def get_input(stream):
    if stream is None or isinstance(stream, FD):
        return stream
    if isinstance(stream, int):
        return FD(stream, 'rb')
    if isinstance(stream, OutputPipe):
        return stream.read_fd
    if isinstance(stream, (Process, Result)):
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

    Feeding the subprocess's stdin after the fact can be done. For small data sizes,
    this is straightforward:

    >>> from pysh import Pipe
    >>> fifo = Pipe(); p = Process('cat', fifo.read_fd, stdout=PIPE)
    >>> fifo.write(b'123'); p.wait().stdout
    3
    b'123'

    However, this will deadlock for large data sizes, which is why InputPipe
    exists. It handles writing to the Pipe in a new thread. This means some
    additional queue-like object is necessary to write data to the InputPipe:

    >>> from pysh import Pipe
    >>> fifo = Pipe(); p = Process('cat', InputPipe(fifo), stdout=PIPE)
    >>> fifo.write(b'x' * 12345678)
    12345678
    >>> res = p.wait()
    >>> len(res.stdout)
    12345678

    and the choice of such object is not especially important:

    >>> from queue import SimpleQueue
    >>> queue = SimpleQueue(); p = Process('cat', InputPipe(queue.get), stdout=PIPE)
    >>> queue.put(b'X' * 12345678)
    >>> res = p.wait()
    >>> len(res.stdout)
    12345678

    Reading data from a running subprocess is also possible. This is easier
    since blocking is not a concern, but there are caveats:
     - the FDs the child is meant to be writing to must be closed in the
       parent (i.e., this "local" process) *first*
     - Process.wait() can't be used since it also tries to read from stdout,
       but there's little benefit to using it anyway
    With that in mind:

    >>> p = Process('cat', b'X' * 12345678, stdout=PIPE)
    >>> p.close_local()
    >>> len(p.stdout.read())
    12345678
    >>> p.waitpid()
    0

    It is also possible to mess around with Process.read() and .read_all() to
    a similar effect, but it is likely not worthwhile. Regardless, whenever
    possible, it is much easier to use Process.wait() and .wait_all().
    """
    def __init__(
        self,
        argv, stdin=None, stdout=None, stderr=None,
        *,
        shell=False, env=None, backend='default', other_streams=(),
    ):
        """initialize the process
        argv:   arguments to process; will be run through shlex.split() if a str and shell=False
        stdin:  input data, generally an int or something with a .fileno() method
                if bytes-like, gets wrapped in an InputPipe
                if Result or Process*, its .stdout is used
        stdout: standard output, generally an int or something with a .fileno() method
                if PIPE == -1, set to an OutputPipe
        stderr: standard error, generally an int or something with a .fileno() method
                if PIPE == -1, set to an OutputPipe
        shell:  whether to run in a shell
                if False-like, don't run in a shell
                if exactly True, run ['sh', '-c', 'argv']
                if str, run through shlex.split() and append '-c' if there's only one token
                otherwise, use as is
        env:    mapping like os.environ; None should inherit os.environ, but it strictly
                depends on the backend
        backend: one of 'default', 'posix_spawn', 'fork_exec' and 'subprocess'.
                 On modern Linux on Python>=3.6, posix_spawn should be the default.
                 If something's not working, 'subprocess' is probably the most robust,
                 but it comes with a lot of baggage.
        other_streams:  add streams other than the standard ones. The format is either
                        { child_fd: stream, ... } or [ stream, ... ]. In the latter case
                        the FDs are enumerated starting at 3 (i.e., right after the std
                        streams). Note that passing other_streams={1: ...} is not exactly
                        the same as passing stdout=... in that Process.wait() will not
                        attempt to manage the stream; however, if manually managing I/O
                        and using Process.waitpid(), there is no difference.

        *If stdin is a process, it is treated specially. In particular Process.waitall() will
        work its way back to it, making sure not to read its own stdout.
        """
        from shlex import split
        self.argv = argv
        self.result = None

        self.backend = get_backend(backend) if isinstance(backend, str) else backend

        if other_streams and self.backend is get_backend('subprocess'):
            raise NotImplementedError("other_streams is not supported with backend='subprocess'")

        if shell:
            if shell is True:
                shell = 'sh -c'
            if isinstance(shell, str):
                shell = split(shell)
                if len(shell) == 1:
                    shell.append('-c')
            shell.append(argv)
            argv = shell
        elif isinstance(argv, str):
            argv = split(argv)

        self.input = stdin if isinstance(stdin, Process) else None
        self.streams = get_input(stdin), get_output(stdout), get_output(stderr)
        streams = { i: s for i, s in enumerate(self.streams) if s is not None }
        n = len(streams)
        m = len(other_streams)
        try:
            streams.update(other_streams)
        except TypeError:
            streams.update(enumerate(other_streams, start=3))
        if n + m != len(streams):
            raise ValueError('duplicate stream specification')
        self.pid = self.backend.spawn(argv, env, streams)

    @classmethod
    def emit(cls, argv, *args, **kwargs):
        r'''same as Process(argv, None, PIPE, *args, **kwargs)

        >>> Process.emit('echo abc').wait()
        Result(argv='echo abc', status=0, stdout=b'abc\n')
        '''
        return cls(argv, None, PIPE, *args, **kwargs)

    def into(self, argv, *args, **kwargs):
        r'''same as Process(argv, self, *args, **kwargs)

        >>> Process.emit('echo abc').into('tr a-z A-Z', stdout=PIPE).wait()
        Result(argv='tr a-z A-Z', status=0, stdout=b'ABC\n')
        '''
        if self.stdout is None:
            raise ValueError(f'{type(self).__name__}({repr(self.argv)}, ...) writes to standard output')
        return type(self)(argv, self, *args, **kwargs)

    def through(self, argv, *args, **kwargs):
        r'''same as self.into(argv, PIPE, self, *args, **kwargs)

        >>> Process.emit('echo abc').through('tr a-z A-Z').wait()
        Result(argv='tr a-z A-Z', status=0, stdout=b'ABC\n')
        '''
        return self.into(argv, PIPE, *args, **kwargs)

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

    def waitpid(self, kill: Signals | int = 0):
        r"""like os.waitpid(), but returns an exit status

        NOTE: you should probably use process.wait().returncode instead

        >>> Process('exit 7').waitpid()
        7
        """
        if kill:
            self.kill(kill)
        return self.backend.wait(self.pid)

    def waitpid_all(self, kill: Signals | int = 0, kill_chain: Signals | int = SIGTERM):
        r"""recursive version of waitpid()

        NOTE: you should probably use process.wait_all() instead

        >>> Process('exit 2', Process('exit 1')).waitpid_all()
        (1, 2)
        """
        status = self.waitpid(kill)
        previous = () if self.input is None else self.input.waitpid_all(kill_chain, kill_chain)
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
        for stream in self.streams:
            if isinstance(stream, (InputPipe, OutputPipe)):
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
            stream.read() if read and stream is not None and stream.readable() else None  # type: ignore
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
        previous = () if self.input is None else self.input.read_all(stdout=False, stderr=True)
        self.close_local()
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

    def wait_all(self, kill: Signals | int = 0, kill_chain: Signals | int = SIGTERM):
        r"""wait on every process of the chain and collect results

        >>> Process('tr a-z A-Z', Process('echo abc', None, PIPE), PIPE).wait_all()
        (Result(argv='echo abc', status=0), Result(argv='tr a-z A-Z', status=0, stdout=b'ABC\n'))
        """
        argvs = self.argv_all()
        outputs = self.read_all()
        statuses = self.waitpid_all(kill, kill_chain)

        results = tuple(
            Result(argv, status, stdout, stderr)
            for argv, status, (stdout, stderr) in zip(argvs, statuses, outputs)
        )
        return results

    def wait(self, kill: Signals | int = 0, kill_chain: Signals | int = SIGTERM):
        r"""short for process.wait_all()[-1]

        >>> Process('tr a-z A-Z', Process('echo abc', None, PIPE), PIPE).wait()
        Result(argv='tr a-z A-Z', status=0, stdout=b'ABC\n')
        """
        return self.wait_all(kill, kill_chain)[-1]

    def kill(self, sig: Signals | int | str = SIGTERM, dead_okay: bool | None = None):
        r"""convenience for os.kill(self.pid, signal)

        sig can be an integer or the signal name, case insensitive, with or
        without the 'SIG' prefix

        dead_okay=False raises ProcessLookupError if the process is dead; by
        default dead_okay=True for SIGTERM and SIGKILL and False otherwise

        NOTE: this follows POSIX kill semantics, not those of `subprocess`; the
        default behavior is to send SIGTERM, not SIGKILL.

        >>> p = Process('sleep 10'); p.kill(); p.wait()
        Result(argv='sleep 10', status=-15)
        >>> p = Process('sleep 10'); p.kill(9); p.wait()
        Result(argv='sleep 10', status=-9)
        >>> p = Process('sleep 10'); p.kill('kill'); p.wait()
        Result(argv='sleep 10', status=-9)
        >>> p = Process('echo', stdout=PIPE); p.wait()
        Result(argv='echo', status=0, stdout=b'\n')
        >>> try: p.kill(dead_okay=False)
        ... except ProcessLookupError: 'no good'
        ...
        'no good'
        """
        sig = get_signal(sig)
        if dead_okay is None:
            dead_okay = sig == SIGTERM or sig == SIGKILL
        try:
            os.kill(self.pid, sig)
        except ProcessLookupError:
            if not dead_okay:
                raise

    def kill_all(self, sig=SIGTERM, dead_okay=None, include_unmanaged=False):
        r'''recursively kill all input processes

        same arguments as .kill() except:
        include_unmanaged: kill all child PIDs, including those not directly
            managed by this Process object or its inputs
            This is useful if one of these processes has its own children.
        '''
        sig = get_signal(sig)
        if dead_okay is None:
            dead_okay = sig == SIGTERM or sig == SIGKILL

        if include_unmanaged:
            for child in children(self.pid):
                try:
                    os.kill(child, sig)
                except ProcessLookupError:
                    if not dead_okay:
                        raise
            self.kill(sig, dead_okay)
        else:
            self.kill(sig, dead_okay)
            if self.input is not None:
                self.input.kill_all(sig, dead_okay)


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
