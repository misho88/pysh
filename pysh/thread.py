__all__ = 'Thread',

import threading


class Thread(threading.Thread):
    """no-frills thread with a return value

    >>> Thread(lambda: 1 + 2).start().join()
    3
    >>> with Thread(lambda: 1 + 2) as thread: thread.join()
    ...
    3
    >>> with Thread(lambda: print('hello')) as thread: pass
    ...
    hello
    """
    def __init__(self, target):
        """initilialize the thread

        target: callable which takes no arguments
        """
        self.result = None

        def closure():
            self.result = target()

        super().__init__(target=closure, name=Thread.get_name(target))

    def start(self):
        """start the thread"""
        super().start()
        return self

    def join(self, timeout=None):
        """join the thread"""
        super().join(timeout)
        return self.result

    @staticmethod
    def get_name(func):
        """give a decent name to the thread"""
        if hasattr(func, 'func') and func.func is not func:
            return Thread.get_name(func.func)
        return repr(func)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.join()
