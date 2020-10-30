r"""wrappers to subprocess.run

pysh exposes several enhanced functions that make calling processes easier,
primarily `proc`, `wait` and `run`, which are similar to `Popen`, `wait` and
`run` from `subprocess`, respectively.

In short, you can write stuff like a shell pipeline:
>>> run.o('echo "1\n2\n3"') | check | get.stdout | to.decode | to.splitlines
['1', '2', '3']

and you can map inputs to pipelines (with unary +):
>>> (1, 2, 3) | +to('expr 1 + {}'.format) | +run.o | +check | +get.o | +to.decode | +to.rstrip | now
('2', '3', '4')

or define some chains separately and spawn the processes at the same time (the
first `now`) so they run in parallel:
>>> (1, 2, 3) | +(to('expr 1 + {}'.format) & proc.o) | now | +(wait&check&get.o&to.decode&to.rstrip) | now
('2', '3', '4')

It uses the `funcpipes` module (https://github.com/misho88/funcpipes) for the
enhanced behavior. See later examples for details.

`run` works more or less like `subprocess.run`, with some shortcuts to common
features:
>>> from pysh import *
>>> run('exit 1')
CompletedProcess(args='exit 1', returncode=1)
>>> run('echo XyZ', stdout=PIPE)
CompletedProcess(args='echo XyZ', returncode=0, stdout=b'XyZ\n')
>>> run.o('echo XyZ')
CompletedProcess(args='echo XyZ', returncode=0, stdout=b'XyZ\n')
>>> run.e('echo XyZ >&2', shell=True)
CompletedProcess(args='echo XyZ >&2', returncode=0, stderr=b'XyZ\n')
>>> run.sh.e('echo XyZ >&2')
CompletedProcess(args='echo XyZ >&2', returncode=0, stderr=b'XyZ\n')
>>> run.sh('echo XyZ; echo AbC >&2', stdout=PIPE, stderr=PIPE)
CompletedProcess(args='echo XyZ; echo AbC >&2', returncode=0, stdout=b'XyZ\n', stderr=b'AbC\n')
>>> run.sh.oe('echo XyZ; echo AbC >&2')
CompletedProcess(args='echo XyZ; echo AbC >&2', returncode=0, stdout=b'XyZ\n', stderr=b'AbC\n')

`wait(proc(...))` also works essentially like `run`, but `run` wraps
`subprocess.run` directly:
>>> wait(proc.o('tr a-z A-Z', b'asdf'))
CompletedProcess(args='tr a-z A-Z', returncode=0, stdout=b'ASDF')

The second argument of `run` and `proc` in `input`, which can be bytes-like
or file-like or a file descriptor and will be transformed into something
`subprocess.Popen` will accept accordingly.
>>> import os
>>> r, w = os.pipe()
>>> with open(w, 'w') as wf: wf.write('XyZ')
...
3
>>> wait(proc.o.with_context('cat', open(r)))
CompletedProcess(args='cat', returncode=0, stdout=b'XyZ')

Checking the result for failure and raising an exception is possible with the
`check` function, which uses `subprocess.check_returncode` to raise a
CalledProcessError:
>>> try:
...     check(run('exit 7'))
... except CalledProcessError as e:
...     print(e)
...
Command 'exit 7' returned non-zero exit status 7.

The more interesting features of `Pipe`s include a shell-like calling syntax,
i.e., `x | f` in lieu of `f(x)` and being able to create partial calls as
`f[x]` in lieu of `functools.partial(f, x)`. This allows for the following:
>>> b'hello' | run.o['tr a-z A-Z'] | get.o
b'HELLO'

"""

__all__ = [
    'Process', 'proc', 'wait', 'run',
    'check', 'die',
    'PIPE',
    'CompletedProcess', 'CalledProcessError',
    'to', 'get', 'now'
]

from subprocess import run as run_, Popen, PIPE, CompletedProcess, CalledProcessError
from typing import Optional
from shlex import split
import os
from functools import wraps
import threading

from funcpipes import Pipe, to, get, now


class Thread(threading.Thread):
    """thread with a return value"""
    def __init__(self, target):
        self.result = None
        def closure():
            self.result = target()
        super().__init__(target=closure)

    def start(self, *args, **kwargs):
        super().start(*args, **kwargs)
        return self

    def join(self, *args, **kwargs):
        super().join(*args, **kwargs)
        return self.result


class Process:
    r"""subprocess.Popen with tweaks

    argv, input, stdout and stderr can be passed positionally
    argv will be split as needed
    input can be used as stdin (file-like or fd) or be memoryview-like
    Popen.communicate() is called immediately 

    >>> Process('echo 123', stdout=PIPE).wait()
    CompletedProcess(args='echo 123', returncode=0, stdout=b'123\n')
    >>> with Process('echo 123', stdout=PIPE) as p: p.wait()
    ... 
    CompletedProcess(args='echo 123', returncode=0, stdout=b'123\n')
    >>> Process('cat >&2', b'123', None, PIPE, shell=True).wait()
    CompletedProcess(args='cat >&2', returncode=0, stderr=b'123')
    """
    def __init__(
        self,
        argv, input=None, stdout=None, stderr=None,
        *, shell=False, **popen_kwargs,
    ):
        """set up the process
        argv: the command line to run as a string or sequence of them
        input: some data, a file-like object or a file descriptor
            (incompatible with the stdin keyword to subprocess.Popen)
        stdout: a file=like object or PIPE
        stderr: a file=like object or PIPE
        shell: True to run in a shell
        popen_kwargs: arguments to pass to subprocess.Popen
        """
        self.argv = argv
        self.input = input

        if not shell and isinstance(argv, str):
            argv = split(argv)
        stdin = popen_kwargs.pop('stdin', None)
        if stdin is not None:  # if stdin is passed directly, honor it
            if input is not None:
                raise ValueError('input and stdin cannot be used simultaneously')
        else:  # normally, try to infer whether input is stdin or data for it
            input = getattr(input, 'stdout', input)
            try:
                input = memoryview(input)
            except TypeError:
                stdin = input
                input = None
            else:
                stdin = PIPE

        self.popen = Popen(
            argv, stdin=stdin, stdout=stdout, stderr=stderr,
            shell=shell, **popen_kwargs,
        )
        
        comm = Pipe(self.popen.communicate).partial(input)
        self.communication_thread = Thread(comm).start()

    def wait(self, timeout=None):
        """wait for the process to finish"""
        returncode = self.popen.wait(timeout=timeout)
        # NOTE: the timeout argument in Popen.wait affects Popen.communicate(),
        # so this join call should be fine:
        outputs = self.communication_thread.join()
        self.result = CompletedProcess(self.argv, returncode, *outputs)
        return self.result

    def poll(self):
        """check if the process is running

        returns None if it is and the returncode if it has finished
        """
        return self.popen.poll()

    def __enter__(self):
        self.popen.__enter__()
        return self

    def __exit__(self, exc_type, value, traceback):
        return self.popen.__exit__(exc_type, value, traceback)


@Pipe
def proc(*args, **kwargs):
    r"""creates a Process

    >>> proc('echo abc', output=PIPE).wait()
    CompletedProcess(args='echo abc', returncode=0, stdout=b'abc\n')
    >>> b'abc' | proc.o['tr a-z A-Z'] | ~wait
    CompletedProcess(args='tr a-z A-Z', returncode=0, stdout=b'ABC')
    >>> b'X' * (1 << 20) | proc.o['cat'] | wait | check | get.o | to(len)
    1048576
    """
    return Process(*args, **kwargs)


wait = to.wait
run = proc & wait.with_context


for func in proc, run:
    func.sh = func.partial(shell=True)

    for w in (func, func.sh):
        w.o = w.partial(stdout=PIPE, stderr=None)
        w.e = w.partial(stdout=None, stderr=PIPE)
        w.oe = w.partial(stdout=PIPE, stderr=PIPE)


@Pipe
def check(result):
    if not isinstance(result, CompletedProcess):
        raise TypeError(f'result must be CompletedProcess, not {type(result)}')
    result.check_returncode()
    return result


@Pipe
def die(result):
    from sys import stderr, exit
    try:
        return check(result)
    except CalledProcessError as e:
        if e.stderr is not None:
            stderr.write(e.stderr)
        exit(e.returncode)


if __name__ == '__main__':
    from doctest import testmod
    testmod()
