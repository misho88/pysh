r"""wrappers to subprocess.run

pysh exposes several enhanced functions that make calling processes easier,
primarily `proc`, `wait` and `run`, which are similar to `Popen`, `wait` and
`run` from `subprocess`, respectively.

In short, you can write stuff like a shell pipeline:
>>> run.o('echo "1\n2\n3"') | check | get.stdout | to.decode | to.splitlines
['1', '2', '3']

and you can map inputs to pipelines (with unary +):
>>> (1, 2, 3) | +to('expr 1 + {}'.format) | +run.o | +check | +get.o | +to.decode | +to.rstrip | now
('2', '3', '4')

or define some chains separately and spawn the processes at the same time (the
first `now`) so they run in parallel:
>>> (1, 2, 3) | +(to('expr 1 + {}'.format) & proc.o) | now | +(wait&check&get.o&to.decode&to.rstrip) | now
('2', '3', '4')

It uses the `funcpipes` module (https://github.com/misho88/funcpipes) for the
enhanced behavior. See later examples for details.

`run` works more or less like `subprocess.run`, with some shortcuts to common
features:
>>> from pysh import *
>>> run('exit 1')
CompletedProcess(args=['exit', '1'], returncode=1)
>>> run('echo XyZ', stdout=PIPE)
CompletedProcess(args=['echo', 'XyZ'], returncode=0, stdout=b'XyZ\n')
>>> run.o('echo XyZ')
CompletedProcess(args=['echo', 'XyZ'], returncode=0, stdout=b'XyZ\n')
>>> run.e('echo XyZ >&2', shell=True)
CompletedProcess(args='echo XyZ >&2', returncode=0, stderr=b'XyZ\n')
>>> run.sh.e('echo XyZ >&2')
CompletedProcess(args='echo XyZ >&2', returncode=0, stderr=b'XyZ\n')
>>> run.sh('echo XyZ; echo AbC >&2', stdout=PIPE, stderr=PIPE)
CompletedProcess(args='echo XyZ; echo AbC >&2', returncode=0, stdout=b'XyZ\n', stderr=b'AbC\n')
>>> run.sh.oe('echo XyZ; echo AbC >&2')
CompletedProcess(args='echo XyZ; echo AbC >&2', returncode=0, stdout=b'XyZ\n', stderr=b'AbC\n')

`wait.with_context(proc(...))` also works essentially like `run`, but `run`
wraps `subprocess.run` directly. `.with_context` is a feature of
`funcpipes.Pipe`, which enters contexts without a `with` statement and can be
omitted if there are no context managers:
>>> wait(proc.o('tr a-z A-Z', b'asdf'))
CompletedProcess(args=['tr', 'a-z', 'A-Z'], returncode=0, stdout=b'ASDF')

The second argument of `run` and `proc` in `input`, which can be bytes-like
or file-like or a file descriptor and will be transformed into something
`subprocess.Popen` will accept accordingly.
>>> import os
>>> r, w = os.pipe()
>>> with open(w, 'w') as wf: wf.write('XyZ')
...
3
>>> wait.with_context(proc.o('cat', open(r)))
CompletedProcess(args=['cat'], returncode=0, stdout=b'XyZ')

Checking the result for failure and raising an exception is possible with the
`check` function, which uses `subprocess.check_returncode` to raise a
CalledProcessError:
>>> try:
...     check(run('exit 7'))
... except CalledProcessError as e:
...     print(e)
...
Command '['exit', '7']' returned non-zero exit status 7.

The more interesting features of `Pipe`s include a shell-like calling syntax,
i.e., `x | f` in lieu of `f(x)` and being able to create partial calls as
`f[3]` in lieu of `functools.partial(f, 3)`. This allows for the following:
>>> b'hello' | run.o['tr a-z A-Z'] | get.o
b'HELLO'

"""

__all__ = [
    'proc', 'wait', 'run',
    'check', 'die',
    'PIPE',
    'CompletedProcess', 'CalledProcessError',
    'to', 'get', 'now'
]

from subprocess import run as run_, Popen, PIPE, CompletedProcess, CalledProcessError
from typing import Optional
from shlex import split
import os
from functools import wraps

from funcpipes import Pipe, to, get, now


def interface(func: callable, name: str, qualname: Optional[str] = None):
    if not isinstance(name, str):
        raise TypeError(f'name must be a str, not {type(name)}')
    if qualname is not None and not isinstance(qualname, str):
        raise TypeError(f'qualname must be a str, not {type(qualname)}')

    @wraps(func)
    def wrapper(argv, input=None, stdout=None, stderr=None, shell=False, **popen_kwargs):
        """wrapper around {name}

        Args:
            argv: what to run; if a str and shell=False, will be run through shlex.split
            input: an input pipe or something to feed into it
                if input has an "stdout" attribute (as a Popen or CompletedProcess would),
                it is used. If it can be turned into a memoryview, it is treated as input
                data. Otherwise, it is passed to {func}.
            stdout: see subprocess.Popen()
            stderr: see subprocess.Popen()
            shell: see subprocess.Popen()
            **popen_kwargs: passed through to subprocess.Popen()

        Returns:
            a CompletedProcess or Popen instance
        """
        if not shell and isinstance(argv, str):
            argv = split(argv)

        stdin = popen_kwargs.pop('stdin', None)
        if stdin is not None:  # if stdin is passed directly, honor it
            if input is not None:
                raise ValueError('input and stdin cannot be used simultaneously')
        else:  # normally, try to infer whether input is stdin or data for it
            input = getattr(input, 'stdout', input)
            try:
                input = memoryview(input)
            except TypeError:
                stdin = input
            else:
                stdin, pwrite = os.pipe()
                with open(pwrite, 'wb') as pfile:
                    pfile.write(input)

        return func(argv, stdin=stdin, stdout=stdout, stderr=stderr, shell=shell, **popen_kwargs)

    wrapper.__doc__ = wrapper.__doc__.format(name=name, func=getattr(func, '__name__', str(func)))
    wrapper.__name__ = name
    wrapper.__qualname__ = name if qualname is None else qualname
    return wrapper


wrappers = []
for func, name in (run_, 'run'), (Popen, 'proc'):
    wrapper = Pipe(interface(func, name))
    wrapper.sh = wrapper.partial(shell=True)

    for w in (wrapper, wrapper.sh):
        w.o = w.partial(stdout=PIPE, stderr=None)
        w.e = w.partial(stdout=None, stderr=PIPE)
        w.oe = w.partial(stdout=PIPE, stderr=PIPE)
    wrappers.append(wrapper)
run, proc = wrappers


@Pipe
def wait(proc, timeout=None):
    """like subprocess.Popen.wait, but returns a CompletedProcess"""
    returncode = proc.wait(timeout=timeout)
    outputs = (
        None if output is None or output.closed else output.read()
        for output in (proc.stdout, proc.stderr)
    )
    return CompletedProcess(proc.args, returncode, *outputs)


@Pipe
def check(result):
    if not isinstance(result, CompletedProcess):
        raise TypeError(f'result must be CompletedProcess, not {type(result)}')
    result.check_returncode()
    return result


@Pipe
def die(result):
    from sys import stderr, exit
    try:
        return check(result)
    except CalledProcessError as e:
        if e.stderr is not None:
            stderr.write(e.stderr)
        exit(e.returncode)


if __name__ == '__main__':
    from doctest import testmod
    testmod()
