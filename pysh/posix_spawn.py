"""low-level module for spawning and waiting for processes with posix_spawn

It only contains two functions, spawn() and wait()


>>> import os
>>> from tempfile import TemporaryDirectory
>>> with TemporaryDirectory() as dir:
...     with open(f'{dir}/file', 'wb') as file:
...         wait(spawn(['echo', 'hello world'], streams=dict(stdout=file)))
...     with open(f'{dir}/file') as file:
...         print(file.read(), end='')
...
0
hello world
"""

__all__ = 'spawn', 'wait'

import os
from .posix_wait import wait
from .spawn_util import get_streams


def spawn(argv, env=None, streams=()):
    """spawn a process and return its pid

    >>> from time import time
    >>> start = time(); pid = spawn(['sleep', '0.2']); wait(pid); print(round(time() - start, 1))
    0
    0.2
    """

    import signal

    if env is None:
        env = os.environb

    file_actions = [
        action
        for child_fd, stream in get_streams(streams)
        for action in (
            (os.POSIX_SPAWN_DUP2, stream.fileno(), child_fd),
            (os.POSIX_SPAWN_CLOSE, stream.fileno()),
        )
    ]

    setsigdef = (getattr(signal, sig, None) for sig in ('SIGPIPE', 'SIGXFZ', 'SIGXFSZ'))
    setsigdef = [ sig for sig in setsigdef if sig is not None ]

    return os.posix_spawnp(
        argv[0], argv, env,
        file_actions=file_actions,
        setsigdef=setsigdef,
    )
