__all__ = 'Pipe', 'InputPipe', 'OutputPipe'

from .util import Thread
from .fd import FD
import os
from functools import partial


class Pipe:
    """wrapper around os.pipe

    >>> p = Pipe()
    >>> p.write(b'hello')
    5
    >>> p.read()
    b'hello'
    """
    def __init__(self, mode='b'):
        """initialize the pipe

        mode: whatever would be passed to open(), except 'r' and 'w' since the
              read endpoint gets and 'r' and the write endpoint a 'w'
        """
        self.fds = tuple(
            FD(fd, f'{rw}{mode}')
            for fd, rw in zip(os.pipe(), 'rw')
        )

    @property
    def read_fd(self):
        return self.fds[0]

    @property
    def write_fd(self):
        return self.fds[1]

    def close(self, invalid_ok=True):
        for fd in self.fds:
            fd.close(invalid_ok)

    def write(self, data):
        with self.write_fd.open() as file:
            return file.write(data)

    def read(self):
        with self.read_fd.open() as file:
            return file.read()

    def __repr__(self):
        return f'{type(self).__name__}()<{self.read_fd}, {self.write_fd}>'

    def readable(self):
        return self.read_fd.readable()

    def writable(self):
        return self.write_fd.writable()


class InputPipe(Pipe):
    """Pipe designed for use as an input to  process

    Creates a thread to feed data into the pipe to remove size limits.
    Also defines suitable fileno() method for use with a subprocess.

    >>> len(InputPipe(b'X' * 12345678).read())
    12345678
    """
    def __init__(self, data, mode='b'):
        super().__init__(mode)
        self.thread = Thread(partial(super().write, data)).start()

    def close_local(self):
        self.read_fd.close()

    def fileno(self):
        return int(self.read_fd)

    def wait(self):
        return self.thread.join()


class OutputPipe(Pipe):
    """Pipe designed for use as the output of a process"""
    def fileno(self):
        return int(self.write_fd)

    def close_local(self):
        self.write_fd.close()
