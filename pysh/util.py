__all__ = (
    'pid', 'pwd', 'cd', 'cwd', 'lsof', 'lsof_iter',
    'to', 'now', 'get', 'Arguments',
    'proc', 'wait', 'check', 'die', 'run',
)

import os
from pathlib import Path

from contextlib import contextmanager
from funcpipes import Pipe, to, now, get, Arguments
from .process import Process, PIPE


@Pipe
def pid():
    """alias for os.getpid()"""
    return os.getpid()


@Pipe
def lsof_iter(pid=None, return_targets=True):
    """list open file descriptors

    if return_targets is True (default), yields (fd, target) tuples
    otherwise, only yields the file descriptors

    This needs /proc to be properly mounted.
    """
    if pid is None:
        pid = os.getpid()
    proc_path = Path('/', 'proc', str(pid), 'fd')
    return (
        (int(fd.name), fd.resolve()) if return_targets else int(fd.name)
        for fd in proc_path.iterdir()
    )


@Pipe
def lsof(pid=None):
    """list open file descriptors

    returns a dict of the form {fd: target}

    This needs /proc to be properly mounted.
    """
    return dict(lsof_iter(pid))


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
