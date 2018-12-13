"""Manages Treadmill applications lifecycle.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import enum

from treadmill import fs
from treadmill import supervisor
from treadmill import trace
from treadmill import utils
from treadmill.trace.app import events

_LOGGER = logging.getLogger(__name__)


ABORTED_UNKNOWN = {
    'why': 'unknown',
    'payload': None,
}


class AbortedReason(enum.Enum):
    """Container abort reasons.
    """
    # W0232: Class has no __init__ method
    # pylint: disable=W0232
    UNKNOWN = 'unknown'
    UNSUPPORTED = 'unsupported'
    INVALID_TYPE = 'invalid_type'
    TICKETS = 'tickets'
    SCHEDULER = 'scheduler'
    PORTS = 'ports'
    PRESENCE = 'presence'
    IMAGE = 'image'
    PID1 = 'pid1'
    GMSA = 'GMSA'
    TIMEOUT = 'timeout'
    PIVOT_ROOT = 'pivot_root'
    FEATURE = 'feature'

    def description(self):
        """Gets the description for the current aborted reason."""
        return {
            AbortedReason.INVALID_TYPE: 'invalid image type',
            AbortedReason.TICKETS: 'tickets could not be fetched',
            AbortedReason.SCHEDULER: 'scheduler error',
            AbortedReason.PORTS: 'ports could not be assigned',
            AbortedReason.IMAGE: 'could not use given image',
            AbortedReason.PID1: 'pid1 failed to start',
            AbortedReason.GMSA: 'host is not part of GMSA group',
            AbortedReason.PIVOT_ROOT: 'pivot_root failure',
            AbortedReason.UNSUPPORTED: 'unsupported on the node',
            AbortedReason.FEATURE: 'failed to configure feature',
        }.get(self, self.value)


def abort(container_dir, why=None, payload=None):
    """Abort a running application.

    Called when some initialization failed in a running container.
    """
    flag_aborted(container_dir, why, payload)
    container_dir = os.path.realpath(os.path.join(container_dir, '../'))
    supervisor.control_service(container_dir,
                               supervisor.ServiceControlAction.down)


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
    if payload is not None:
        payload = str(payload)

    fs.write_safe(
        os.path.join(container_dir, 'aborted'),
        lambda f: f.writelines(
            utils.json_genencode(
                {
                    'why': _why_str(why),
                    'payload': payload
                }
            )
        ),
        mode='w',
        permission=0o644
    )


def report_aborted(tm_env, instance, why=None, payload=None):
    """Report an aborted instance.

    Called when aborting after failed configure step or from cleanup.
    """
    if payload is not None:
        payload = str(payload)

    trace.post(
        tm_env.app_events_dir,
        events.AbortedTraceEvent(
            instanceid=instance,
            why=_why_str(why),
            payload=payload
        )
    )
