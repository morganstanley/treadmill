"""App trace events.
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


class AppTraceEvent(_events.TraceEvent):
    """Parent class of all app trace events.

    Contains the basic attributes of all events as well as the factory method
    `from_data` that instanciate an event object from its data representation.

    All app event classes must derive from this class.
    """

    __slots__ = (
        'event_type',
        'timestamp',
        'source',
        'instanceid',
        'payload',
    )

    def __init__(self,
                 timestamp=None, source=None, instanceid=None, payload=None):
        self.event_type = AppTraceEventTypes(self.__class__).name
        if timestamp is None:
            self.timestamp = None
        else:
            self.timestamp = float(timestamp)
        self.source = source
        self.payload = payload
        self.instanceid = instanceid

    @property
    @abc.abstractmethod
    def event_data(self):
        """Return an event's event_data.
        """

    @classmethod
    def _class_from_type(cls, event_type):
        """Return the class for a given event_type.
        """
        etype = getattr(AppTraceEventTypes, event_type, None)
        if etype is None:
            _LOGGER.warning('Unknown event type %r', event_type)
            return None
        eclass = etype.value
        return eclass

    @classmethod
    def from_data(cls, timestamp, source, instanceid, event_type, event_data,
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
                instanceid=instanceid,
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
            self.instanceid,
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


class ScheduledTraceEvent(AppTraceEvent):
    """Event emitted when a container instance is placed on a node.
    """

    __slots__ = (
        'where',
        'why',
    )

    def __init__(self, where, why,
                 timestamp=None, source=None, instanceid=None, payload=None):
        super(ScheduledTraceEvent, self).__init__(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload
        )
        self.where = where
        self.why = why

    @classmethod
    def from_data(cls, timestamp, source, instanceid, event_type, event_data,
                  payload=None):
        assert cls == getattr(AppTraceEventTypes, event_type).value

        if ':' in event_data:
            where, why = event_data.split(':', 1)
        else:
            where = event_data
            why = None

        return cls(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload,
            where=where,
            why=why,
        )

    @property
    def event_data(self):
        return '%s:%s' % (self.where, self.why)


class PendingTraceEvent(AppTraceEvent):
    """Event emitted when a container instance is seen by the scheduler but not
    placed on a node.
    """

    __slots__ = (
        'why',
    )

    def __init__(self, why,
                 timestamp=None, source=None, instanceid=None, payload=None):
        super(PendingTraceEvent, self).__init__(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload
        )
        self.why = why

    @classmethod
    def from_data(cls, timestamp, source, instanceid, event_type, event_data,
                  payload=None):
        assert cls == getattr(AppTraceEventTypes, event_type).value
        return cls(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload,
            why=event_data
        )

    @property
    def event_data(self):
        return self.why


class PendingDeleteTraceEvent(AppTraceEvent):
    """Event emitted when a container instance is about to be deleted from the
       scheduler.
    """

    __slots__ = (
        'why',
    )

    def __init__(self, why,
                 timestamp=None, source=None, instanceid=None, payload=None):
        super(PendingDeleteTraceEvent, self).__init__(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload
        )
        self.why = why

    @classmethod
    def from_data(cls, timestamp, source, instanceid, event_type, event_data,
                  payload=None):
        assert cls == getattr(AppTraceEventTypes, event_type).value
        return cls(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload,
            why=event_data
        )

    @property
    def event_data(self):
        return self.why


class ConfiguredTraceEvent(AppTraceEvent):
    """Event emitted when a container instance is configured on a node.
    """

    __slots__ = (
        'uniqueid',
    )

    def __init__(self, uniqueid,
                 timestamp=None, source=None, instanceid=None, payload=None):
        super(ConfiguredTraceEvent, self).__init__(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload
        )
        self.uniqueid = uniqueid

    @classmethod
    def from_data(cls, timestamp, source, instanceid, event_type, event_data,
                  payload=None):
        assert cls == getattr(AppTraceEventTypes, event_type).value
        return cls(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload,
            uniqueid=event_data
        )

    @property
    def event_data(self):
        return self.uniqueid


class DeletedTraceEvent(AppTraceEvent):
    """Event emitted when a container instance is deleted from the scheduler.
    """

    __slots__ = (
    )

    @classmethod
    def from_data(cls, timestamp, source, instanceid, event_type, event_data,
                  payload=None):
        assert cls == getattr(AppTraceEventTypes, event_type).value
        return cls(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload
        )

    @property
    def event_data(self):
        pass


class FinishedTraceEvent(AppTraceEvent):
    """Event emitted when a container instance finished.
    """

    __slots__ = (
        'rc',
        'signal',
    )

    def __init__(self, rc, signal,
                 timestamp=None, source=None, instanceid=None, payload=None):
        super(FinishedTraceEvent, self).__init__(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload
        )
        self.rc = int(rc)
        self.signal = int(signal)

    @classmethod
    def from_data(cls, timestamp, source, instanceid, event_type, event_data,
                  payload=None):
        assert cls == getattr(AppTraceEventTypes, event_type).value
        rc, signal = event_data.split('.', 2)
        return cls(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload,
            rc=rc,
            signal=signal
        )

    @property
    def event_data(self):
        return '{rc}.{signal}'.format(
            rc=self.rc,
            signal=self.signal
        )


class AbortedTraceEvent(AppTraceEvent):
    """Event emitted when a container instance was aborted.
    """

    __slots__ = (
        'why',
    )

    def __init__(self, why,
                 timestamp=None, source=None, instanceid=None, payload=None):
        super(AbortedTraceEvent, self).__init__(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload
        )
        self.why = why

    @classmethod
    def from_data(cls, timestamp, source, instanceid, event_type, event_data,
                  payload=None):
        assert cls == getattr(AppTraceEventTypes, event_type).value
        return cls(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload,
            why=event_data
        )

    @property
    def event_data(self):
        return self.why


class KilledTraceEvent(AppTraceEvent):
    """Event emitted when a container instance was killed.
    """

    __slots__ = (
        'is_oom',
    )

    def __init__(self, is_oom,
                 timestamp=None, source=None, instanceid=None, payload=None):
        super(KilledTraceEvent, self).__init__(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload
        )
        self.is_oom = is_oom

    @classmethod
    def from_data(cls, timestamp, source, instanceid, event_type, event_data,
                  payload=None):
        assert cls == getattr(AppTraceEventTypes, event_type).value
        return cls(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload,
            is_oom=(event_data == 'oom')
        )

    @property
    def event_data(self):
        return '{oom}'.format(
            oom=('oom' if self.is_oom else '')
        )


class ServiceRunningTraceEvent(AppTraceEvent):
    """Event emitted when a service of container instance started.
    """

    __slots__ = (
        'uniqueid',
        'service',
    )

    def __init__(self, uniqueid, service,
                 timestamp=None, source=None, instanceid=None, payload=None):
        super(ServiceRunningTraceEvent, self).__init__(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload
        )
        self.uniqueid = uniqueid
        self.service = service

    @classmethod
    def from_data(cls, timestamp, source, instanceid, event_type, event_data,
                  payload=None):
        assert cls == getattr(AppTraceEventTypes, event_type).value
        parts = event_data.split('.')
        uniqueid = parts.pop(0)
        service = '.'.join(parts)
        return cls(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload,
            uniqueid=uniqueid,
            service=service
        )

    @property
    def event_data(self):
        return '{uniqueid}.{service}'.format(
            uniqueid=self.uniqueid,
            service=self.service
        )


class ServiceExitedTraceEvent(AppTraceEvent):
    """Event emitted when a service of container instance exited.
    """

    __slots__ = (
        'uniqueid',
        'service',
        'rc',
        'signal',
    )

    def __init__(self, uniqueid, service, rc, signal,
                 timestamp=None, source=None, instanceid=None, payload=None):
        super(ServiceExitedTraceEvent, self).__init__(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload
        )
        self.uniqueid = uniqueid
        self.service = service
        self.rc = int(rc)
        self.signal = int(signal)

    @classmethod
    def from_data(cls, timestamp, source, instanceid, event_type, event_data,
                  payload=None):
        assert cls == getattr(AppTraceEventTypes, event_type).value

        parts = event_data.split('.')
        uniqueid = parts.pop(0)
        signal = parts.pop()
        rc = parts.pop()
        service = '.'.join(parts)

        return cls(
            timestamp=timestamp,
            source=source,
            instanceid=instanceid,
            payload=payload,
            uniqueid=uniqueid,
            service=service,
            rc=rc,
            signal=signal
        )

    @property
    def event_data(self):
        return '{uniqueid}.{service}.{rc}.{signal}'.format(
            uniqueid=self.uniqueid,
            service=self.service,
            rc=self.rc,
            signal=self.signal
        )


class AppTraceEventTypes(enum.Enum):
    """Enumeration of all app event type names.
    """
    aborted = AbortedTraceEvent
    configured = ConfiguredTraceEvent
    deleted = DeletedTraceEvent
    finished = FinishedTraceEvent
    killed = KilledTraceEvent
    pending = PendingTraceEvent
    pending_delete = PendingDeleteTraceEvent
    scheduled = ScheduledTraceEvent
    service_exited = ServiceExitedTraceEvent
    service_running = ServiceRunningTraceEvent


class AppTraceEventHandler(_events.TraceEventHandler):
    """Base class for processing app trace events.
    """

    DISPATCH = {
        ScheduledTraceEvent:
            lambda self, event: self.on_scheduled(
                when=event.timestamp,
                instanceid=event.instanceid,
                server=event.where,
                why=event.why
            ),
        PendingTraceEvent:
            lambda self, event: self.on_pending(
                when=event.timestamp,
                instanceid=event.instanceid,
                why=event.why
            ),
        PendingDeleteTraceEvent:
            lambda self, event: self.on_pending_delete(
                when=event.timestamp,
                instanceid=event.instanceid,
                why=event.why
            ),
        DeletedTraceEvent:
            lambda self, event: self.on_deleted(
                when=event.timestamp,
                instanceid=event.instanceid
            ),
        ConfiguredTraceEvent:
            lambda self, event: self.on_configured(
                when=event.timestamp,
                instanceid=event.instanceid,
                server=event.source,
                uniqueid=event.uniqueid
            ),
        FinishedTraceEvent:
            lambda self, event: self.on_finished(
                when=event.timestamp,
                instanceid=event.instanceid,
                server=event.source,
                exitcode=event.rc,
                signal=event.signal
            ),
        AbortedTraceEvent:
            lambda self, event: self.on_aborted(
                when=event.timestamp,
                instanceid=event.instanceid,
                server=event.source,
                why=event.why
            ),
        KilledTraceEvent:
            lambda self, event: self.on_killed(
                when=event.timestamp,
                instanceid=event.instanceid,
                server=event.source,
                is_oom=event.is_oom
            ),
        ServiceRunningTraceEvent:
            lambda self, event: self.on_service_running(
                when=event.timestamp,
                instanceid=event.instanceid,
                server=event.source,
                uniqueid=event.uniqueid,
                service=event.service
            ),
        ServiceExitedTraceEvent:
            lambda self, event: self.on_service_exited(
                when=event.timestamp,
                instanceid=event.instanceid,
                server=event.source,
                uniqueid=event.uniqueid,
                service=event.service,
                exitcode=event.rc,
                signal=event.signal
            ),
    }

    def dispatch(self, event):
        """Dispatch event to one of the handler methods.
        """
        return self.DISPATCH.get(type(event), None)

    @abc.abstractmethod
    def on_scheduled(self, when, instanceid, server, why):
        """Invoked when task is scheduled.
        """

    @abc.abstractmethod
    def on_pending(self, when, instanceid, why):
        """Invoked when task is pending.
        """

    @abc.abstractmethod
    def on_pending_delete(self, when, instanceid, why):
        """Invoked when task is about to be deleted.
        """

    @abc.abstractmethod
    def on_configured(self, when, instanceid, server, uniqueid):
        """Invoked when task is configured.
        """

    @abc.abstractmethod
    def on_deleted(self, when, instanceid):
        """Invoked when task is deleted.
        """

    @abc.abstractmethod
    def on_finished(self, when, instanceid, server, signal, exitcode):
        """Invoked when task is finished.
        """

    @abc.abstractmethod
    def on_aborted(self, when, instanceid, server, why):
        """Invoked when task is aborted.
        """

    @abc.abstractmethod
    def on_killed(self, when, instanceid, server, is_oom):
        """Default task-finished handler.
        """

    @abc.abstractmethod
    def on_service_running(self, when, instanceid, server, uniqueid, service):
        """Invoked when service is running.
        """

    @abc.abstractmethod
    def on_service_exited(self, when, instanceid, server, uniqueid, service,
                          exitcode, signal):
        """Invoked when service exits.
        """
