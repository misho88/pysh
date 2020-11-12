"""low-level module for spawning and waiting for processes with subprocess.Popen

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

from subprocess import Popen

spawned = {}


def spawn(argv, env=None, stdin=None, stdout=None, stderr=None):
    popen = Popen(argv, env=env, stdin=stdin, stdout=stdout, stderr=stderr)
    spawned[popen.pid] = popen
    return popen.pid


def wait(pid):
    if pid in spawned:
        return spawned.pop(pid).wait()
    from .posix_wait import wait
    return wait(pid)
