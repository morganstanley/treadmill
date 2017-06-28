"""Manages Treadmill applications lifecycle."""

from __future__ import absolute_import

import json
import logging
import os

import enum

from treadmill import appevents
from treadmill import supervisor
from treadmill.apptrace import events

_LOGGER = logging.getLogger(__name__)


class AbortedReason(enum.Enum):
    """Container abort reasons.
    """
    # W0232: Class has no __init__ method
    # pylint: disable=W0232
    UNKNOWN = 'unknown'
    INVALID_TYPE = 'invalid_type'
    TICKETS = 'tickets'
    SCHEDULER = 'scheduler'
    PORTS = 'ports'
    PRESENCE = 'presence'

    def description(self):
        """Gets the description for the current aborted reason."""
        return {
            AbortedReason.INVALID_TYPE: 'invalid image type',
            AbortedReason.TICKETS: 'tickets could not be fetched',
            AbortedReason.SCHEDULER: 'scheduler error',
            AbortedReason.PORTS: 'ports could not be assigned',
        }.get(self, self.value)


def abort(container_dir, why=None, payload=None):
    """Abort a running application.

    Called when some initialization failed in a running container.
    """
    flag_aborted(container_dir, why, payload)
    container_dir = os.path.realpath(os.path.join(container_dir, '../'))
    supervisor.control_service(container_dir,
                               supervisor.ServiceControlAction.kill)


def _why_str(why):
    """Gets the string for app aborted reason."""
    if isinstance(why, AbortedReason):
        return why.value

    return str(why)


def flag_aborted(container_dir, why=None, payload=None):
    """Flags container as aborted.

    Called when aborting in failed run step.
    Consumed by cleanup script.
    """
    with open(os.path.join(container_dir, 'aborted'), 'w+') as f:
        json.dump({
            'why': _why_str(why),
            'payload': str(payload)
        }, f)


def report_aborted(tm_env, instance, why=None, payload=None):
    """Report an aborted instance.

    Called when aborting after failed configure step or from cleanup.
    """
    appevents.post(
        tm_env.app_events_dir,
        events.AbortedTraceEvent(
            why=_why_str(why),
            instanceid=instance,
            payload=str(payload)
        )
    )
