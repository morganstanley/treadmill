"""Event processing engine logic implementations.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import fnmatch
import heapq
import io
import logging
import math
import signal
import time
import collections
import re

import six

_LOGGER = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class BaseEventEngine(object):
    """base abstract classs for policy engine """

    def __init__(self, sender):
        self._policy = collections.defaultdict(dict)
        self._sender = sender
        self._ready = False

    def __repr__(self):
        return str(self._policy)

    def del_policy(self, name):
        """Delete an policy
        """
        for policies in self._policy.values():
            policies.pop(name, None)

    def add_policy(self, name, definition):
        """Abstract method to add definition
        """
        (pattern, exits, pending) = definition

        # extract proid
        # TODO: personal containers?
        (proid, _) = pattern.split('.', 1)

        # prepare pattern to make it recognize instance
        if pattern.find('#') == -1:
            pattern = pattern + '#*'

        pattern = re.compile(fnmatch.translate(pattern))

        self._policy[proid][name] = (pattern, exits, pending)

    def find_policy(self, instanceid):
        """Return matching policy for instance
        """
        # TODO: personal containers?
        (proid, _) = instanceid.split('.', 1)

        policies = self._policy.get(proid)
        if policies:
            for (pattern, exits, pending) in policies.values():
                if pattern.match(instanceid):
                    return (exits, pending)

        return (None, None)

    @abc.abstractmethod
    def process(self, event, path=None):
        """Abstract method to process event
        """
        pass

    def ready(self):
        """Mark engine as ready
        """
        self._ready = True

    def send(self, event, event_item, event_time=None):
        """Send event via sender
        """
        payload = event.to_dict()
        instanceid = payload.pop('instanceid')
        self._sender.send(event_item, payload, instanceid, event_time)


class PendingEventEngine(BaseEventEngine):
    """Pending APP Policy Engine"""

    _EVENT_ITEM = 'container.pending'

    def __init__(self, sender):
        super(PendingEventEngine, self).__init__(sender)
        self._pending_queue = []
        self._pending = {}
        signal.signal(signal.SIGALRM, self._alarm_handler)

    def ready(self):
        """When ready, we need to kick off alarm
        """
        super(PendingEventEngine, self).ready()
        if len(self._pending_queue) > 0:
            self._set_alarm()

    def _next_alarm(self):
        """Determine after how many seconds will next alarm signal triggered
        """
        return int(math.ceil(self._pending_queue[0][0] - time.time()))

    def _set_alarm(self):
        """Set next alarm signal
        """
        # if not ready, it means the engine is still collecting history data
        # from the sproc startup stage
        if self._ready:
            signal.alarm(max(self._next_alarm(), 1))

    def _alarm_handler(self, *_):
        """Alarm hanlder of sigalarm
        """
        while len(self._pending_queue) > 0:

            if self._next_alarm() > 0:
                self._set_alarm()
                break

            (_t, pending) = heapq.heappop(self._pending_queue)

            # If instance after pending status, just ignore it
            if self._pending.pop(pending.instanceid, None) is None:
                continue

            self.send(pending, self._EVENT_ITEM, time.time())

    def _clear_alarm(self):
        """clear alarm signal being set.
        If an alarm signal being set, move it back to alarm queue.
        Wait for next around alarm signal set
        """
        if self._ready:
            signal.alarm(0)

    def process(self, event, path=None):
        """Process an event
        """
        # this means master start to schedule the instance
        if event.event_type == 'pending':

            (_exits, pending) = self.find_policy(event.instanceid)
            if not pending:
                return

            _LOGGER.debug(
                'New pending event, %s, %s, %s',
                event.instanceid, event.source, event.timestamp
            )

            self._clear_alarm()
            heapq.heappush(
                self._pending_queue, (event.timestamp + pending, event)
            )
            self._pending[event.instanceid] = True
            self._set_alarm()

        # this means instance configured on node server
        elif (event.event_type == 'configured' or
              event.event_type == 'aborted' or
              event.event_type == 'deleted'):

            (_exits, pending) = self.find_policy(event.instanceid)
            if not pending:
                return

            _LOGGER.debug(
                'Pending event %s, %s, %s, %s',
                event.event_type, event.instanceid, event.source,
                event.timestamp
            )

            self._pending.pop(event.instanceid, None)


class ExitEventEngine(BaseEventEngine):
    """APP Exit Policy Engine
    """

    _EVENT_ITEM = 'container.exit'

    _EXIT_TYPE = {
        'non-zero':
            lambda et: et.event_type == 'finished' and et.rc != 0,
        'oom':
            lambda et: et.event_type == 'killed' and et.is_oom,
        'aborted':
            lambda et: et.event_type == 'aborted',
    }

    def process(self, event, path=None):
        """Process an event
        """
        if (event.event_type == 'finished' or
                event.event_type == 'aborted' or
                event.event_type == 'killed'):

            (exits, _pending) = self.find_policy(event.instanceid)
            if not exits:
                return

            for exit_type in exits:
                if self._EXIT_TYPE[exit_type](event):
                    if path is not None:
                        try:
                            with io.open(path) as f:
                                event.payload = f.read()
                        except IOError:
                            _LOGGER.warning('%s deleted', path)
                    # if event sent, then process complete
                    self.send(event, self._EVENT_ITEM, event.timestamp)
                    return
