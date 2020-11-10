from doctest import testmod
from . import fd, thread, pipe, posix, process, util

for mod in fd, thread, pipe, posix, process, util:
    print(f'testing {mod}...')
    testmod(mod)
