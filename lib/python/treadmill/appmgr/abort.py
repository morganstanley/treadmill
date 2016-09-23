"""Manages Treadmill applications lifecycle."""
from __future__ import absolute_import

import logging
import os

from .. import appevents


_LOGGER = logging.getLogger(__name__)


def abort(tm_env, event, exc=None):
    """Abort a unconfigured application.

    Called when aborting after failed configure step.
    """
    # If aborting after failed configure step, the 'name' attibute is
    # derived from the event file name.
    app_name = os.path.basename(event)
    _LOGGER.info('Aborting %s', app_name)

    # Report start failure.
    reason = None
    if exc:
        reason = str(exc)

    # TODO: need to provide short description of aborted reason.
    appevents.post(tm_env.app_events_dir, app_name, 'aborted', None, reason)


def flag_aborted(_tm_env, container_dir, exc=None):
    """Flags container as aborted.

    Called when aborting in failed run step.
    Consumed by cleanup script.
    """
    with open(os.path.join(container_dir, 'aborted'), 'w+') as f:
        if exc:
            f.write(str(exc))
