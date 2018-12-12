"""Trace events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import logging

_LOGGER = logging.getLogger(__name__)


class TraceEvent(abc.ABC):
    """Abstract base class of all trace events.
    """

    @abc.abstractmethod
    def to_data(self):
        """Return a 6 tuple represtation of an event.
        """

    @abc.abstractmethod
    def to_dict(self):
        """Return a dictionary representation of an event.
        """

    def __repr__(self):
        return '{classname}<{data}>'.format(
            classname=self.__class__.__name__[:-len('TraceEvent')],
            data=self.to_dict()
        )

    def __eq__(self, other):
        return (
            type(self) is type(other) and
            self.to_dict() == other.to_dict()
        )


class TraceEventHandler(abc.ABC):
    """Abstract base class for processing trace events.
    """

    __slots__ = (
        'ctx',
    )

    def __init__(self):
        self.ctx = None

    @abc.abstractmethod
    def dispatch(self, event):
        """Dispatch event to one of the handler methods.
        """

    def process(self, event, ctx=None):
        """Process a given event dispatching to one of the handler methods.

        :param `TraceEvent` event:
            Event to process.
        :param ctx:
            Contextual reference passed around (available from handlers).
        """
        event_handler = self.dispatch(event)
        if event_handler is None:
            _LOGGER.warning('No handler for event %r', event)
            return

        try:
            self.ctx = ctx
            event_handler(self, event)
        finally:
            self.ctx = None
