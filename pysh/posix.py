"""low-level module for spawning and waiting for processes on POSIX systems

It only contains two functions, spawn() and wait()


>>> import os
>>> from tempfile import TemporaryDirectory
>>> with TemporaryDirectory() as dir:
...     with open(f'{dir}/file', 'wb') as file:
...         wait(spawn(['echo', 'hello world'], stdout=file))
...     with open(f'{dir}/file') as file:
...         print(file.read(), end='')
...
0
hello world
"""

__all__ = 'spawn', 'wait'

import os


def spawn(argv, env=None, stdin=None, stdout=None, stderr=None):
    """spawn a process and return its pid

    >>> from time import time
    >>> start = time(); pid = spawn(['sleep', '0.2']); wait(pid); print(round(time() - start, 1))
    0
    0.2
    """

    import signal

    if env is None:
        env = os.environb

    streams = stdin, stdout, stderr
    file_actions = [
        (os.POSIX_SPAWN_DUP2, stream.fileno(), child_fd)
        for child_fd, stream in enumerate(streams)
        if stream is not None
    ] + [
        (os.POSIX_SPAWN_CLOSE, stream.fileno())
        for child_fd, stream in enumerate(streams)
        if stream is not None
    ]

    setsigdef = (getattr(signal, sig, None) for sig in ('SIGPIPE', 'SIGXFZ', 'SIGXFSZ'))
    setsigdef = [ sig for sig in setsigdef if sig is not None ]

    return os.posix_spawnp(
        argv[0], argv, env,
        file_actions=file_actions,
        setsigdef=setsigdef,
    )


def wait(pid):
    """wait on a pid to complete

    >>> from time import time
    >>> start = time(); pid = spawn(['sleep', '0.2']); wait(pid); print(round(time() - start, 1))
    0
    0.2
    """
    pid_, status = os.waitpid(pid, 0)
    if pid_ == pid:
        if os.WIFSIGNALED(status):
            returncode = -os.WTERMSIG(status)
        elif os.WIFEXITED(status):
            returncode = os.WEXITSTATUS(status)
        elif os.WIFSTOPPED(status):
            returncode = -os.WSTOPSIG(status)
        else:
            raise RuntimeError(f'weird exit status: 0x{hex(pid)}')
    else:
        raise RuntimeError(f'pid is {pid_}, expected {pid}')
    return returncode
