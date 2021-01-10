__all__ = 'FD',

import os
from errno import EBADF
from functools import partial, cached_property

try:
    import fcntl
except ImportError:
    fcntl = None


if fcntl is not None:
    def get_cmd(cmd):
        return getattr(fcntl, cmd.upper()) if isinstance(cmd, str) else cmd

    def get_arg(arg):
        return getattr(os, arg.upper()) if isinstance(arg, str) else arg

    def make_property(arg):
        arg = get_arg(arg)

        def get(self):
            return self.get(arg)

        def set(self, value):
            return self.set(arg, value)

        return property(get).setter(set)

    class Flags:
        NAMES = (
            'O_RDONLY', 'O_WRONLY', 'O_RDWR', 'O_ACCMODE', 'O_CREAT', 'O_EXCL',
            'O_NOCTTY', 'O_TRUNC', 'O_APPEND', 'O_NONBLOCK', 'O_DSYNC', 'O_ASYNC',
            'O_DIRECT', 'O_DIRECTORY', 'O_NOFOLLOW', 'O_NOATIME', 'O_CLOEXEC',
            'O_SYNC', 'O_PATH', 'O_TMPFILE'
        )

        def __init__(self, fd):
            self.fd = fd

        @property
        def mask(self):
            return fcntl.fcntl(self.fd, fcntl.F_GETFL)

        @mask.setter
        def mask(self, value):
            return fcntl.fcntl(self.fd, fcntl.F_SETFL, value)

        def get(self, flag):
            flag = get_arg(flag)
            return bool(self.mask & flag)

        def set(self, flag, value=1):
            from fcntl import fcntl, F_GETFL, F_SETFL
            if value not in (0, 1, False, True):
                raise ValueError('value must be 0/1 or False/True')
            flag = get_arg(flag)
            mask = self.mask
            mask = mask | flag if value else mask & ~flag
            self.mask = mask

        def unset(self, flag):
            self.set(flag, 0)

        locals().update((n, make_property(n)) for n in NAMES)


class FD:
    """file descriptor wrapper

    A glorified integer with a close() method.

    >>> from os import pipe
    >>> r, w = pipe()
    >>> rfd, wfd = FD(r, 'r'), FD(w, 'w')
    >>> with wfd.open() as file: file.write('test')
    ...
    4
    >>> with rfd.open() as file: file.read()
    ...
    'test'
    """
    def __init__(self, fd, mode='r'):
        self.fd = int(fd)
        self.mode = mode

    def fileno(self):
        return self.fd

    def open(self):
        return open(self.fd, self.mode)

    def close(self, invalid_ok=True):
        try:
            os.close(self.fd)
        except OSError as e:
            if not invalid_ok or e.errno != 9:
                raise

    @property
    def closed(self):
        try:
            os.stat(self.fd)
        except OSError as e:
            if e.errno != EBADF:
                raise
            return True
        else:
            return False

    def readable(self):
        return any(c in self.mode for c in 'r+') and not self.closed

    def writable(self):
        return any(c in self.mode for c in 'wxa+') and not self.closed

    def __repr__(self):
        return f'{type(self).__name__}({self.fd}, {repr(self.mode)})'

    def __int__(self):
        return self.fd

    if fcntl is not None:
        def fcntl(self, cmd, arg=0):
            """calls fcntl.fcntl with this FD as the FD argument

            Additionally, cmd and arg can be strings that will be treated as
            attributes of fcntl and os, respectively.
            """
            if isinstance(cmd, str):
                cmd = getattr(fcntl, cmd.upper())
            if isinstance(arg, str):
                arg = getattr(os, arg.upper())
            return fcntl.fcntl(self.fd, cmd, arg)

        @cached_property
        def flags(self):
            """access to FD flags"""
            return Flags(self.fd)
