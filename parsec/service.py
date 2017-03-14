from blinker import signal

from parsec.exceptions import ParsecError


class CmdWrap:
    def __init__(self, name, callback):
        self.name = name
        self.callback = callback

    def __call__(self, *args, **kwargs):
        return self.callback(*args, **kwargs)


class EventWrap:
    def __init__(self, name):
        self.name = name
        self.event = signal(name)


def event(name):
    return EventWrap(name)


def cmd(param):
    if callable(param):
        return CmdWrap(param.__name__, param)
    else:
        return lambda fn: CmdWrap(param, fn)


class MetaBaseService(type):

    def __new__(cls, name, bases, nmspc):
        cmd_keys = {}
        events = {}
        cooked_nmspc = {'_cmd_keys': cmd_keys, '_events': events}
        for b in bases:
            cmd_keys.update(getattr(b, '_cmd_keys', {}))
            events.update(getattr(b, '_events', {}))
        # Retrieve new cmd and event here
        # TODO: check for overwritten cmd/events ?
        for k, v in nmspc.items():
            if isinstance(v, CmdWrap):
                cmd_keys[k] = v.name
                cooked_nmspc[k] = v.callback
            elif isinstance(v, EventWrap):
                events[v.name] = v.event
                cooked_nmspc[k] = v.event
            else:
                cooked_nmspc[k] = v
        # Build the actual type and register the list of events&cmds
        return type.__new__(cls, name, bases, cooked_nmspc)


class BaseService(metaclass=MetaBaseService):
    def __init__(self):
        super().__init__()
        self._cmds = {}

    @property
    def cmds(self):
        # Lazy load commands to get them binded to the self object
        if not self._cmds:
            self._cmds = {name: getattr(self, field) for field, name in self._cmd_keys.items()}
        return self._cmds

    @property
    def events(self):
        return self._events

    async def dispatch_msg(self, msg):
        try:
            return await self.cmds[msg['cmd']](msg)
        except ParsecError as exc:
            return exc.to_dict()
