# pysh - PYthon SHell

In a few words, `pysh` is like `subprocess` but a bit more flexible and powerful. I also think it's a bit more intuitive, but that's subjective.

## Description

The initial goal was to have something that allows syntax similar to the Bourne shell in Python, but due to limitations in `subprocess`, it became necessary to essentially implement most of its functionality from scratch. As a result, `pysh` also became a convenient way to launch subprocesses. As a result, there's a clean and powerful object-oriented API and the shell-like one. Both have their use cases, but since the latter is built on the former, that will be described first.

## Object-Oriented API

The aforementioned limitations of `subprocess` primarily had essentially one root cause: all sorts of functionaly distinct features are implemented as part of `subprocess.Popen` in a way that makes it difficult to decouple them. As a result, in `pysh`, these are implemented separately and include:
 - file descriptors (`pysh.fd`)
 - pipes (`pysh.pipe`)
 - processes (`pysh.process`)

### File Descriptors

`pysh.fd.FD` is a simple object that wraps an integer that represents a file descriptor. It tacks on a few useful methods and properties, however, like `.fileno()`, `.open()`, `.close()`, `.closed`, `.readable()`, and `.writable()`, which more or less make it file-like. At instantiation, it requires a mode which will later be passed to `.open()`. 

Example usage follows:
```
>>> from os import pipe
>>> r, w = pipe()
>>> rfd, wfd = FD(r, 'r'), FD(w, 'w')
>>> with wfd.open() as file: file.write('test')
...
4
>>> with rfd.open() as file: file.read()
...
'test'
```

### Pipes

`pysh.pipe.Pipe` wraps `os.pipe`, managing its two outputs as `pysh.fd.FD`s and providing `.write()` and `.read()` methods:
```
>>> p = Pipe()
>>> p.write(b'hello')
5
>>> p.read()
b'hello'
```
A common issue with pipes in Unix is that they have a limited capacity and block when full, which becomes a problem when reading and writing is not concurrent. For this reason, the `.write()` method will accept various sources of data, rather than just `bytes`-like objects, so that it can easily be passed to another thread, such as generators and callables (the docstring has details):
```
>>> f = Pipe(); f.write(str(i).encode() for i in (1, 2, 3)); f.read()
3
b'123'
>>> f = Pipe(); f.write(lambda file: file.write(b'123')); f.read()
3
b'123'
```
There are two subclasses of `Pipe`, `InputPipe` and `OutputPipe`, which are meant to be used as inputs and outputs to subprocesses, respectively. One common requirement once a file descriptor has been duplicated to a child process is to close its local counterpart (i.e., the read FD of the input pipe and the write FD of the output pipe), so these define appropriate `.close_local()` methods. Additionally, the input pipe takes its input source at instantiation and spawns a thread to write to the pipe. This means that it can pipe more data that it can hold at a time without much effort:
```
>>> len(InputPipe(b'X' * 12345678).read())
12345678
```
### Processes
`pysh.process.Process` is a bit like `subprocess.Popen`, but significantly easier to work with. For example, piping the output of one process to another works:
```
>>> p = Process('tr a-z A-Z', b'x' * 12345678, stdout=PIPE)
>>> q = Process('cat', p, stdout=PIPE)
>>> len(q.wait().stdout)
12345678
```
Managing I/O by hand is straightforward:
```
>>> inp = InputPipe(b'X' * 10 for _ in range(10))
>>> out = OutputPipe()
>>> prc = Process('cat', inp, out)
>>> out.close_local()
>>> len(out.read())
100
>>> prc.wait()
Result(argv='cat', status=0)
```
Letting `Process` deal with most of it is fine, too, although it's arguably a bad idea with large data streams:
```
>>> len(Process('cat', InputPipe(b'X' * 10 for _ in range(10)), PIPE).wait().stdout)
100
```
Since the I/O is primarily dealt with via `Pipe` objects, `Process` really does very little here. The main exception is when chaining processes together, wherein each `Process` makes sure its data source is taken care of. It therefore only makes sense to manage the first input in the chain and the last output (i.e., the same limitation you have when piping commands in a shell).

Process also takes a `shell=` argument that can be used to run the command in a shell, although the main point of `pysh` is to supplant shells from inside Python, so it's not very useful. The `env=` argument specifies environement variables and is empty by default (i.e., it is not `sys.environ`).

The `backend=` argument describes how the process will be spawned. The default on Linux is to try to use `posix_spawn`, failing that a pure-Python fork-exec implementation, and failing that, just wrapping `subprocess.Popen`. A specific one can be forced, but they all basically do the same thing.

## The Shell-Like API

This API provides a terse way of spawning multiple child processes. The functions for this are in `pysh.util`. They make use of the `funcpipes` module (https://github.com/misho88/funcpipes/).  It is perhaps easiest to just show several equivalent ways of doing the same thing:
```
>>> Process('echo hello', stdout=PIPE).wait()
Result(argv='echo hello', status=0, stdout=b'hello\n')
>>> proc('echo hello', stdout=PIPE).wait()
Result(argv='echo hello', status=0, stdout=b'hello\n')
>>> proc.o('echo hello').wait()
Result(argv='echo hello', status=0, stdout=b'hello\n')
>>> proc.o('echo hello') | wait
Result(argv='echo hello', status=0, stdout=b'hello\n')
>>> run.o('echo hello')
Result(argv='echo hello', status=0, stdout=b'hello\n')
```
The last two of these are the most shell-like. The main difference between `proc` and `Process` is that `proc` is a `funcpipes.Pipe` which is a fancy function that can, among other things, easily generate partial applications of itself. The following are thus equivalent:
```
>>> Process('tr a-z A-Z', Process('echo hello', None, PIPE), PIPE).wait()
Result(argv='tr a-z A-Z', status=0, stdout=b'HELLO\n')
>>> proc.o('echo hello') | proc.o.partial('tr a-z A-Z') | wait
Result(argv='tr a-z A-Z', status=0, stdout=b'HELLO\n')
>>> proc.o('echo hello') | proc.o['tr a-z A-Z'] | wait
Result(argv='tr a-z A-Z', status=0, stdout=b'HELLO\n')
```
Note that the shell-like syntax really is easier to read the standard Python. It is also possible to define the command chain ahead of time
```
>>> chain = proc.o['echo hello'] & proc.o['tr a-z A-Z'] & wait
>>> chain()
Result(argv='tr a-z A-Z', status=0, stdout=b'HELLO\n')
```
and to map the same chain to multiple inputs to be executed in parallel:
```
>>> 'abc' | +to.encode | +proc.o['tr a-z A-Z'] | now | +wait | -to(print).partial(sep='\n')
Result(argv='tr a-z A-Z', status=0, stdout=b'A')
Result(argv='tr a-z A-Z', status=0, stdout=b'B')
Result(argv='tr a-z A-Z', status=0, stdout=b'C')
```
Details on how this works are in the example below and here: https://github.com/misho88/funcpipes/

### Complex Example

We're going to load some data from the `ip` utility of `iproute2` using JSON, extracting, say, ip and route data. To do that, we'll import `pysh` and `json`:
```
>>> from pysh import *
>>> import json
```
Next, we describe what we want the execution of `ip` to look like, where `&` denotes function composition. That is, `&` is a bit like `|` but we can supply the input argument later at the expense of having to create the composed function. Ultimately, the line means to pass an input argument to `'ip -json {} show'.format` and then use the result as the input argument to `proc.o`:
```
>>> start = to('ip -json {} show'.format) & proc.o
```
Then we describe what we want to happen to the output of each `ip` command. We want to wait for it to finish (and get its result, a `pysh.Process.Result`), check that everything went well (which raises an error if `ip` returned a nonzero returncode), get the `stdout` property of the result, and pass that onto `json.loads` which will parse it:
```
>>> finish = wait & check & get.stdout & to(json.loads)
```
For a given command, we can then do this:
```
>>> data = 'addr' | start | finish
>>> data
[{'ifindex': 1, ...
```
More interestingly, we can map a sequence of inputs to commands. We use `+start`, which is equivalent to `start.map`, which is roughly equivalent to `lambda args: map(start, args)` (similarly for `+finish`), and `now` which is roughly equivalent to `to(tuple)` and forces the map (the generator) to be evaluated immediately, and thus starts execution. The next synchronization point is in evaluating results for `addr_data` and `route_data`, which is after execution has finished. Therefore, the two subprocesses run in parallel:
```
>>> addr_data, route_data = ('addr', 'route') | +start | now | +finish
>>> addr_data
[{'ifindex': 1, ...
>>> route_data
[{'dst': 'default', ...
```
Mostly to show off, rather than because this is a good way to write code, we can also get more creative with the data extraction, say to get the IP addresses:
```
>>> 'addr' | start | finish \  # this gets us the JSON data, a list of dicts
... | +to.get['addr_info'] \   # for each dict in the list, call get('addr_info'), which is a list of dicts
... | ++to.get['local'] \      # for each addr_info, for each dict, call get('local')
... | now                      # evaluate all the maps (basically to(tuple) but recursive)
(('127.0.0.1', '::1'), ('10.0.0.5', 'fe80::63f3:9b3c:a5c:aef1'), (), (), ('10.8.2.2', 'fe80::a532:3957:2e6
4:4a6a'))
```

## Dependencies:

funcpipes: https://github.com/misho88/funcpipes/
