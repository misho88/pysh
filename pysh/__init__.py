"""pysh - subprocess-like library for spawning child processes

It's possible to run Processes, sort of like subprocess.Popen():

>>> Process('tr a-z A-Z', b'abc', PIPE).wait().check()
Result(argv='tr a-z A-Z', status=0, stdout=b'ABC')

and there's a proc() helper, which can be used the same way:

>>> proc('echo abc', stdout=PIPE).wait().check()
Result(argv='echo abc', staotus=0, stdout=b'abc\n')

but also supports partial application:

>>> p = proc.partial('tr a-z A-Z', stdout=PIPE)
>>> p(b'abc').wait()
Result(argv='tr a-z A-Z', status=0, stdout=b'ABC')
>>> p(b'xyz').wait()
Result(argv='tr a-z A-Z', status=0, stdout=b'XYZ')

and being called via |, like in a shell:

>>> b'abc' | p | wait | check
Result(argv='tr a-z A-Z', status=0, stdout=b'ABC')

The common use case where we want to capture stdout has an alias:

>>> b'abc' | proc.o.partial('tr a-z A-Z') | wait | check
Result(argv='tr a-z A-Z', status=0, stdout=b'ABC')

And positional-only partials can be created via []:
>>> b'abc' | proc.o['tr a-z A-Z'] | wait | check
Result(argv='tr a-z A-Z', status=0, stdout=b'ABC')

Processes can be chained together:
>>> proc.o('echo abc') | proc.o['tr a-z A-Z'] | wait | check
Result(argv='tr a-z A-Z', status=0, stdout=b'ABC\n')

A pipeline of actions can be stored as such:

>>> capitalize = proc.o['tr a-z A-Z'] & wait & check
>>> b'abc' | capitalize
Result(argv='tr a-z A-Z', status=0, stdout=b'ABC')

A few helpers exist, like `to` to call a fucntion or method and
`get` to get a property:

>>> pre = to.encode & proc.o['tr a-z A-Z']
>>> post = wait & check & get.stdout & to.decode
>>> 'abc' | pre | post
'ABC'

At this point, it should be clear that `wait` aliases `to.wait` and
`check` `to.check`.

It is possible to do mapping-style application (+func and func.map are
equivalent):

>>> ('abc', 'xyz') | +pre | now | +post | now
('ABC', 'XYZ')

Generators are lazily evaluated, so `now` is used to force synchronization,
with the meaning that all processes should be created at the first `now` and
their results evaluated at the second `now`. In a flat list, `now` can be
considered at alias of `to(tuple)`. It is generally recursive. It could be
argued that it is more clear to end with a `to(tuple)` or `to(list)` than
`now`. Operations between barrier points (like `now`) happen in parallel:

>>> pipeline = +proc['sleep 0.2'] & now & +wait & to(tuple)
>>> start = time(); results = [Arguments()] * 10 | pipeline; round(time() - start, 1)
0.2

Arguments can be used in places where there is no convenient Python syntax,
in this case, to indicate no arguments. Also, it can be used to just hold
arguments for later use.

There's a run() that works similarly to subprocess.run(). It is literally defined
as `proc & wait`. Note that with `run`, parallel execution is not possible.

>>> echo = to.decode & to(print).partial(end='')
>>> b'xyz\nabc\n' | echo
xyz
abc
>>> b'xyz\nabc\n' | run.o['tr a-z A-Z'] | run.o['sort'] | get.stdout | echo
ABC
XYZ

Using the system shell is possible. The following are exactly equivalent:

>>> run.o('echo abc | tr a-z A-Z', shell=True)
Result(argv='echo abc | tr a-z A-Z', status=0, stdout=b'ABC\n')
>>> run.o('echo abc | tr a-z A-Z', shell='sh')
Result(argv='echo abc | tr a-z A-Z', status=0, stdout=b'ABC\n')
>>> run.o('echo abc | tr a-z A-Z', shell='sh -c')
Result(argv='echo abc | tr a-z A-Z', status=0, stdout=b'ABC\n')
>>> run.sh.o('echo abc | tr a-z A-Z')
Result(argv='echo abc | tr a-z A-Z', status=0, stdout=b'ABC\n')

and the following is functionally equivalent:

>>> run.o('sh -c "echo abc | tr a-z A-Z"')
Result(argv='sh -c "echo abc | tr a-z A-Z"', status=0, stdout=b'ABC\n')

And the shell can be changed:

>>> run('[ -n "$BASH_VERSION" ]', shell='bash').status
0
>>> run('[ -n "$BASH_VERSION" ]', shell='zsh').status
1
>>> run('[ -n "$ZSH_VERSION" ]', shell='bash').status
1
>>> run('[ -n "$ZSH_VERSION" ]', shell='zsh').status
0
"""

from .fd import FD  # noqa: F401
from .pipe import Pipe, InputPipe, OutputPipe  # noqa: F401
from .process import *  # noqa: F401
from .util import *  # noqa: F401 F403

from funcpipes import Pipe as _Pipe, to, now, get, Arguments  # noqa: F401


