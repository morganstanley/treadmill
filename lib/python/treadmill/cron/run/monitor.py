"""
Treadmill schedule monitor event.

This module allows the treadmill cron to take actions on applications,
for example, start and stop them at a given time.
"""

import logging

from treadmill import context
from treadmill import master

_LOGGER = logging.getLogger(__name__)


def set_count(monitor_name=None, count=None):
    """Set the count on the supplied monitor"""
    _LOGGER.debug('monitor_name: %s', monitor_name)
    _LOGGER.debug('count: %s', count)

    zkclient = context.GLOBAL.zk.conn

    if not monitor_name:
        _LOGGER.error('No monitor name supplied, cannot continue')
        return

    master.update_appmonitor(zkclient, monitor_name, count)
