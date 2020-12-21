"""low-level module for spawning and waiting for processes with subprocess.Popen

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

from subprocess import Popen
from .spawn_util import get_streams

spawned = {}


def spawn(argv, env=None, streams=()):
    streams = get_streams(streams, include_None=True, ensure_std=True, std_names=True)
    popen = Popen(argv, env=env, **dict(streams))
    spawned[popen.pid] = popen
    return popen.pid


def wait(pid):
    if pid in spawned:
        return spawned.pop(pid).wait()
    from .posix_wait import wait
    return wait(pid)
