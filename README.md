# pysh - Subprocess with Shell-Like Syntax

This provides a way to describe some (possibly parallel) execution flow succinctly and then run that flow for given inputs.

## Dependencies:

funcpipes: https://github.com/misho88/funcpipes/

## Very Simple Example

You can pipe stuff almost like in a shell with `run`, which runs each process to completion, `run.o` means to capture standard output, and `[]` creates a partial function application:
```
>>> run.o('cal') | run.o['grep Su'] | get.stdout
b'Su Mo Tu We Th Fr Sa\n'
```
or, with `proc`, the processes will actually run at the same time and we only wait for the last to complete: 
```
>>> proc.o('cal') | proc.o['grep Su'] | wait | get.stdout
b'Su Mo Tu We Th Fr Sa\n'
```
and, this is usually better, where `~run(...)` or `run(...).with_context` enter contexts for all arguments that support it:
```
>>> proc.o('cal') | ~run.o['grep Su'] | get.stdout
b'Su Mo Tu We Th Fr Sa\n'
```

## Example

We're going to load some data from the `ip` utility of `iproute2` using JSON, extracting, say, ip and route data. To do that, we'll import pysh and JSON:
```
>>> from pysh import *
>>> import json
```
Next, we describe what we want the execution of `ip` to look like, where `&` denotes function composition. That is, `&` is a bit like `|` but we can supply the input argument later at the expense of having to create the composed function. Ultimately, the line means to pass an input argument to `'ip -json {} show'.format` and then use the result as the input argument to `proc.o`:
```
>>> start = to('ip -json {} show'.format) & proc.o
```
Then we describe what we want to happen to the output of each `ip` command. We want to wait for it to finish (and get its result, a `subprocess.CompletedProcess`), check that everything went well (which raises an error if `ip` returned a nonzero returncode), get the `stdout` property of the result, and pass that onto `json.loads` which will parse it:
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
