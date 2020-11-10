__all__ = (
    'pwd', 'cd', 'cwd',
    'to', 'now', 'get', 'Arguments',
    'proc', 'wait', 'check', 'die', 'run',
)

import os

from contextlib import contextmanager
from funcpipes import Pipe, to, now, get, Arguments
from .process import Process, PIPE


@Pipe
def pwd():
    """alias for os.getcwdb()

    >>> cd('/'); pwd()
    b'/'
    """
    return os.getcwdb()


@Pipe
def cd(path):
    """alias for os.chdir(), but returns the resultant directory

    >>> cd('/tmp')
    b'/tmp'
    >>> cd('..')
    b'/'
    """
    os.chdir(path)
    return pwd()


@contextmanager
def cwd(path):
    """temporarily changes the working directory

    >>> cd('/')
    b'/'
    >>> with cwd('tmp') as dir: print(dir)
    ...
    b'/tmp'
    >>> pwd()
    b'/'
    """
    orig = pwd()
    yield cd(path)
    cd(orig)


@Pipe
def proc(*args, **kwargs):
    r"""creates a Process, see help(Process)"""
    return Process(*args, **kwargs)


wait = to.wait
check = to.check
die = to.die
run = proc & wait

for func in proc, run:
    func.sh = func.partial(shell=True)

    for w in (func, func.sh):
        w.o = w.partial(stdout=PIPE, stderr=None)
        w.e = w.partial(stdout=None, stderr=PIPE)
        w.oe = w.partial(stdout=PIPE, stderr=PIPE)
