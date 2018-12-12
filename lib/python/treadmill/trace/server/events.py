"""Server trace events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import enum  # pylint: disable=wrong-import-order
import logging

from .. import _events

_LOGGER = logging.getLogger(__name__)


class ServerTraceEvent(_events.TraceEvent):
    """Parent class of all server trace events.

    Contains the basic attributes of all events as well as the factory method
    `from_data` that instanciate an event object from its data representation.

    All server event classes must derive from this class.
    """

    __slots__ = (
        'event_type',
        'timestamp',
        'source',
        'servername',
        'payload',
    )

    def __init__(self,
                 timestamp=None, source=None, servername=None, payload=None):
        self.event_type = ServerTraceEventTypes(self.__class__).name
        if timestamp is None:
            self.timestamp = None
        else:
            self.timestamp = float(timestamp)
        self.source = source
        self.payload = payload
        self.servername = servername

    @property
    @abc.abstractmethod
    def event_data(self):
        """Return an event's event_data.
        """

    @classmethod
    def _class_from_type(cls, event_type):
        """Return the class for a given event_type.
        """
        etype = getattr(ServerTraceEventTypes, event_type, None)
        if etype is None:
            _LOGGER.warning('Unknown event type %r', event_type)
            return None
        eclass = etype.value
        return eclass

    @classmethod
    def from_data(cls, timestamp, source, servername, event_type, event_data,
                  payload=None):
        """Intantiate an event from given event data.
        """
        eclass = cls._class_from_type(event_type)
        if eclass is None:
            return None

        try:
            event = eclass.from_data(
                timestamp=timestamp,
                source=source,
                servername=servername,
                event_type=event_type,
                event_data=event_data,
                payload=payload
            )
        except Exception:  # pylint: disable=broad-except
            _LOGGER.warning('Failed to parse event type %r:', event_type,
                            exc_info=True)
            event = None

        return event

    def to_data(self):
        """Return a 6 tuple represtation of an event.
        """
        event_data = self.event_data
        if event_data is None:
            event_data = ''

        return (
            self.timestamp,
            self.source,
            self.servername,
            self.event_type,
            event_data,
            self.payload
        )

    @classmethod
    def from_dict(cls, event_data):
        """Instantiate an event from a dict of its data.
        """
        event_type = event_data.pop('event_type')
        eclass = cls._class_from_type(event_type)
        if eclass is None:
            return None

        try:
            event = eclass(**event_data)

        except Exception:  # pylint: disable=broad-except
            _LOGGER.warning('Failed to instanciate event type %r:', event_type,
                            exc_info=True)
            event = None

        return event

    def to_dict(self):
        """Return a dictionary representation of an event.
        """
        return {
            k: getattr(self, k)
            for k in super(self.__class__, self).__slots__ + self.__slots__
        }


class ServerStateTraceEvent(ServerTraceEvent):
    """Event emitted when server state changes.
    """

    __slots__ = (
        'state',
    )

    def __init__(self, state,
                 timestamp=None, source=None, servername=None, payload=None):
        super(ServerStateTraceEvent, self).__init__(
            timestamp=timestamp,
            source=source,
            servername=servername,
            payload=payload
        )
        self.state = state

    @classmethod
    def from_data(cls, timestamp, source, servername, event_type, event_data,
                  payload=None):
        assert cls == getattr(ServerTraceEventTypes, event_type).value
        return cls(
            timestamp=timestamp,
            source=source,
            servername=servername,
            payload=payload,
            state=event_data
        )

    @property
    def event_data(self):
        return self.state


class ServerBlackoutTraceEvent(ServerTraceEvent):
    """Event emitted when server is blackedout.
    """

    __slots__ = (
    )

    @classmethod
    def from_data(cls, timestamp, source, servername, event_type, event_data,
                  payload=None):
        assert cls == getattr(ServerTraceEventTypes, event_type).value
        return cls(
            timestamp=timestamp,
            source=source,
            servername=servername,
            payload=payload
        )

    @property
    def event_data(self):
        pass


class ServerBlackoutClearedTraceEvent(ServerTraceEvent):
    """Event emitted when server blackout is cleared.
    """

    __slots__ = (
    )

    @classmethod
    def from_data(cls, timestamp, source, servername, event_type, event_data,
                  payload=None):
        assert cls == getattr(ServerTraceEventTypes, event_type).value
        return cls(
            timestamp=timestamp,
            source=source,
            servername=servername,
            payload=payload
        )

    @property
    def event_data(self):
        pass


class ServerTraceEventTypes(enum.Enum):
    """Enumeration of all server event type names.
    """
    server_state = ServerStateTraceEvent
    server_blackout = ServerBlackoutTraceEvent
    server_blackout_cleared = ServerBlackoutClearedTraceEvent


class ServerTraceEventHandler(_events.TraceEventHandler):
    """Base class for processing server trace events.
    """

    DISPATCH = {
        ServerStateTraceEvent:
            lambda self, event: self.on_server_state(
                when=event.timestamp,
                servername=event.servername,
                state=event.state
            ),
        ServerBlackoutTraceEvent:
            lambda self, event: self.on_server_blackout(
                when=event.timestamp,
                servername=event.servername
            ),
        ServerBlackoutClearedTraceEvent:
            lambda self, event: self.on_server_blackout_cleared(
                when=event.timestamp,
                servername=event.servername
            ),
    }

    def dispatch(self, event):
        """Dispatch event to one of the handler methods.
        """
        return self.DISPATCH.get(type(event), None)

    @abc.abstractmethod
    def on_server_state(self, when, servername, state):
        """Invoked when server state changes.
        """

    @abc.abstractmethod
    def on_server_blackout(self, when, servername):
        """Invoked when server is blackedout.
        """

    @abc.abstractmethod
    def on_server_blackout_cleared(self, when, servername):
        """Invoked when server blackout is cleared.
        """
