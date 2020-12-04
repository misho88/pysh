__all__ = 'Pipe', 'InputPipe', 'OutputPipe'

from .thread import Thread
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

    def write(self, data_or_source):
        """open the write FD, feed it some data and close it

        Since this is meant to be a one-off operation, it's a bit more
        flexible than a traditiona write.

        If data_or_source is bytes-like, it works the same way:
        >>> f = Pipe(); f.write(b'123'); f.read()
        3
        b'123'

        If data_or_source is file-like and has a read() method, it tries to use it:
        >>> f = Pipe(); g = Pipe()
        >>> f.write(b'123'); g.write(f); g.read()
        3
        3
        b'123'

        If data_or_source has an open() method like FD.open(), it uses it:
        >>> f = Pipe(); g = Pipe()
        >>> f.write(b'123'); g.write(f.read_fd); g.read()
        3
        3
        b'123'

        If data_or_source is callable, calls it:
        >>> f = Pipe(); f.write(lambda: b'123'); f.read()
        3
        b'123'

        Some more flexibility is available if source takes exactly 1 positional argument:
        >>> f = Pipe(); f.write(lambda file: file.write(b'123')); f.read()
        3
        b'123'

        And generators are honored (as expressions or separate defs):
        >>> f = Pipe(); f.write(str(i).encode() for i in (1, 2, 3)); f.read()
        3
        b'123'

        It does *not* automatically open strings as file paths or or integers
        as file descriptors these must be appropriately handled externally.
        """
        from types import GeneratorType

        with self.write_fd.open() as file:
            try:
                data = memoryview(data_or_source)
            except TypeError:
                source = data_or_source
                if callable(getattr(source, 'read', None)):
                    return file.write(source.read())
                if callable(getattr(source, 'open', None)):
                    with source.open() as stream:
                        return file.write(stream.read())
                if callable(source):
                    try:
                        data = source()
                    except TypeError as e:
                        if 'missing 1 required positional argument' not in e.args[0]:
                            raise
                        return source(file)
                    else:
                        return file.write(data)
                if isinstance(source, GeneratorType):
                    size = 0
                    for line in source:
                        size += file.write(line)
                        file.flush()
                    return size
                raise
            else:
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

    This means that feeding more data than a Pipe can take is nonblocking:
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
