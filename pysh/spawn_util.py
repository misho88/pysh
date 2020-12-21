def get_streams(streams, include_None=False, std_names=False, ensure_std=False):
    if isinstance(streams, dict):
        if ensure_std:
            tmp = { i: None for i in (0, 1, 2) }
            tmp.update(streams)
            streams = tmp
        for fd, stream in streams.items():
            try:
                fd = get_streams.std_names[fd] if std_names else get_streams.std_names.index(fd)
            except (TypeError, IndexError, ValueError):
                pass
            if include_None or stream is not None:
                yield fd, stream
    else:
        streams = tuple(streams)
        if ensure_std:
            streams += (None,) * (3 - len(streams))
        for fd, stream in enumerate(streams):
            if std_names and fd < len(get_streams.std_names):
                fd = get_streams.std_names[fd]
            if include_None or stream is not None:
                yield fd, stream


get_streams.std_names = 'stdin', 'stdout', 'stderr'
