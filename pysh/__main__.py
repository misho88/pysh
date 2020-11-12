from doctest import testmod
from . import fd, thread, pipe, posix_spawn, fork_exec, subprocess, process, util

from .process import change_default_backend, get_backend

print('checking backends...')
for mod in posix_spawn, fork_exec, subprocess:
    print(f'\t{mod.__name__}...')
    testmod(mod)
print()

for backend in 'posix_spawn', 'fork_exec', 'subprocess':
    change_default_backend(backend)
    print(f'with backend {get_backend.default.__name__}...')
    for mod in fd, thread, pipe, process, util:
        print(f'\t{mod.__name__}...')
        testmod(mod)
    print()
