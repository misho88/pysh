"""low-level module for spawning and waiting for processes with os.fork and os.exec

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
import signal
from .posix_wait import wait
from .pipe import Pipe
from .spawn_util import get_streams


def spawn(argv, env=None, streams=()):
    launch_pipe = Pipe()

    pid = os.fork()
    if pid:
        launch_pipe.write_fd.close()
        error = launch_pipe.read()
        if error:
            from ast import literal_eval
            import builtins
            name, argstr = error.decode().split('\n', maxsplit=1)
            error = getattr(builtins, name)
            args = literal_eval(argstr)
            raise error(*args)
        return pid

    for name in 'SIGPIPE', 'SIGXFZ', 'SIGXFSZ':
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        signal.signal(sig, signal.SIG_DFL)

    for i, stream in get_streams(streams):
        fd = stream.fileno()
        os.dup2(fd, i)
        os.close(fd)

    launch_pipe.read_fd.close()
    try:
        os.execvpe(argv[0], argv, env)
        raise RuntimeError('failed to launch process')
    except Exception as e:
        launch_pipe.write('\n'.join((
            type(e).__name__,
            repr(e.args)
        )).encode())
