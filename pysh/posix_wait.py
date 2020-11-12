__all__ = 'wait',

import os


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
