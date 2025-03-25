__all__ = (
    'pids',
    'iter_status', 'status', 'owned',
    'find_pids', 'find_pid',
    'tasks', 'children',
)

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
    try:
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
    except FileNotFoundError as e:
        raise ProcessLookupError from e


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


def find_pids(**kwargs):
    '''find PIDs by their status

    e.g., find_pids(Name='bash') to find the PIDs of scripts
    '''
    for pid in pids():
        if all(status(pid, key) == value for key, value in kwargs.items()):
            yield pid


def find_pid(**kwargs):
    '''same as next(find_pids(**kwargs))'''
    return next(find_pids(**kwargs))


def tasks(pid):
    '''get a list of all tasks in /proc/$PID/task

    There is usually one task, and that task is $PID.
    '''
    try:
        for file in listdir(f'/proc/{pid}/task'):
            yield int(file)
    except FileNotFoundError as e:
        raise ProcessLookupError from e


def children(pid, recursive=False, include_parent=False):
    '''get every child process of PID

    if recursive: look for children of children
    if include_parent: yield pid at the end
    '''
    try:
        for task in tasks(pid):
            with open(f'/proc/{pid}/task/{task}/children') as file:
                for child in file.read().split():
                    child = int(child)
                    if recursive:
                        yield from children(child)
                    yield child
        if include_parent:
            yield pid
    except FileNotFoundError as e:
        raise ProcessLookupError from e
