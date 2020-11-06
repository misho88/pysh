__all__ = 'FD',

import os
from errno import EBADF


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
    def __init__(self, fd, mode):
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
