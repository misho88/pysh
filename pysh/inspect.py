__all__ = 'pids', 'iter_status', 'status', 'owned', 'tasks', 'children'

from os import listdir, getuid


def pids():
    '''yield all PIDs in /proc'''
    for file in listdir('/proc'):
        try:
            yield int(file)
        except ValueError:
            pass


def iter_status(pid):
    '''yield all key-value pairs in /proc/$PID/status'''
    with open(f'/proc/{pid}/status') as file:
        for line in file:
            key, tail = line.split(':\t', maxsplit=1)
            try:
                yield key, int(tail)
                continue
            except ValueError:
                pass
            try:
                yield key, [ int(value) for value in tail.split() ]
                continue
            except ValueError:
                pass
            yield key, tail.removesuffix('\n')


def status(pid, key=None):
    '''get the PID status

    if key is None, returns a dictionary of the whole status
    if key is not None, look up the key and return its value
    '''
    return dict(iter_status(pid)) if key is None else next(
        v
        for k, v in iter_status(pid)
        if key == k
    )


def owned(pid, uid=None):
    '''check if pid is owned by uid (defaulting to getuid())'''
    if uid is None:
        uid = getuid()
    return status(pid, 'Uid')[0] == uid  # type: ignore


def tasks(pid):
    '''get a list of all tasks in /proc/$PID/task

    There is usually one task, and that task is $PID.
    '''
    for file in listdir(f'/proc/{pid}/task'):
        yield int(file)


def children(pid, recursive=False, include_pid=False):
    '''get every child process of PID

    if recursive: look for children of children
    if include_pid: yield pid first
    '''
    if include_pid:
        yield pid
    for task in tasks(pid):
        with open(f'/proc/{pid}/task/{task}/children') as file:
            for child in file.read().split():
                child = int(child)
                yield child
                if recursive:
                    yield from children(child)
