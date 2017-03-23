"""Manages Treadmill applications lifecycle."""


import logging
import os

from treadmill import appevents
from treadmill.apptrace import events

_LOGGER = logging.getLogger(__name__)


def abort(tm_env, event, exc=None, reason=None):
    """Abort a unconfigured application.

    Called when aborting after failed configure step.
    """
    # If aborting after failed configure step, the 'name' attibute is
    # derived from the event file name.
    instanceid = os.path.basename(event)
    _LOGGER.info('Aborting %s', instanceid)

    # Report start failure.
    if reason is None and exc:
        reason = type(exc).__name__

    appevents.post(
        tm_env.app_events_dir,
        events.AbortedTraceEvent(
            why=reason,
            instanceid=instanceid,
            payload=None
        )
    )


def flag_aborted(_tm_env, container_dir, exc=None):
    """Flags container as aborted.

    Called when aborting in failed run step.
    Consumed by cleanup script.
    """
    with open(os.path.join(container_dir, 'aborted'), 'w+') as f:
        if exc:
            f.write(str(exc))
