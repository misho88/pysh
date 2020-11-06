from doctest import testmod
from . import fd, util, pipe, posix, process

for mod in fd, util, pipe, posix, process:
    print(f'testing {mod}...')
    testmod(mod)
