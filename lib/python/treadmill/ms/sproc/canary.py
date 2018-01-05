"""
Run a server that stays connected to all the servers in the specified cell,
and if any of them get dropped, throw a Netcool alert.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time

import click
from kazoo.protocol import states
from kazoo.handlers import threading

from treadmill import context
from treadmill import zkutils

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import alert as treadmill_alert

SLEEP_TIME = 360
# This is the maximum time the start will try to connect for, i.e. 5 secs
ZK_MAX_CONN_START_TIMEOUT = 10
# This is the maximum number of connection tries to all servers in the list
ZK_MAX_CONNECTION_TRIES = 1

EVENT_TYPE = 'cell.zk_canary'

_LOGGER = logging.getLogger(__name__)


def send_alert(summary, alert_key):
    """Sending Watchtower alerts"""
    treadmill_alert.send_event(
        event_type=EVENT_TYPE,
        instanceid=alert_key,
        summary=summary,
    )


class ZKConnectionHandler(object):
    """Simple class to hold the cell and specific ZK instance

    Also handles state or connection changes
    """
    def __init__(self, cell):
        """Construct a new ZKConnectionHandler

        :param cell: the cell name for this connection handler
        :type cell: str
        """
        self.cell = cell
        self.lost = False
        self.initial_connect = True

    def conn_change(self, state):
        """Watch for connection events and exit if disconnected."""
        _LOGGER.info('ZK connection state: %s', state)

        cell = self.cell
        alert_key = '%s/%s' % (cell, state)

        if state == states.KazooState.LOST:
            msg = 'Lost connection to Zookeeper host {cell}'.format(
                cell=cell,
            )
            _LOGGER.error(msg)

            if not self.initial_connect:
                send_alert(msg, alert_key)

            self.lost = True

        elif state == states.KazooState.CONNECTED:
            msg = 'Connected to Zookeeper host {cell}'.format(
                cell=cell,
            )
            _LOGGER.warning(msg)

            if not self.initial_connect and self.lost:
                send_alert(msg, alert_key)
                self.lost = False

        _LOGGER.debug('initial_connect: %s', self.initial_connect)
        if self.initial_connect:
            self.initial_connect = False


def init():
    """Main command handler."""

    @click.command()
    def canary():
        """
        Run a server that stays connected to a cell zk servers,
        and if any of them get dropped, throw a Netcool alert.
        """
        cell = context.GLOBAL.cell
        zklistener = ZKConnectionHandler(cell)
        zkhandler = threading.SequentialThreadingHandler()

        while True:
            try:
                zkclient = zkutils.connect(
                    context.GLOBAL.zk.url,
                    handler=zkhandler,
                    listener=zklistener.conn_change,
                    max_tries=ZK_MAX_CONNECTION_TRIES,
                    timeout=ZK_MAX_CONN_START_TIMEOUT
                )

                if zkclient.connected:
                    _LOGGER.info('We are now connected to %s Zookeepers', cell)
                    break
            except zkhandler.timeout_exception:
                summary = 'Cannot connect to Zookeeper cell {cell}'.format(
                    cell=cell
                )
                _LOGGER.error('Timeout: %s', summary)
                if zklistener.initial_connect:
                    send_alert(summary, '{}/{}'.format(cell, 'init_fail'))
                    # This handles sending an alert when we initially fail and
                    # connect after retrying
                    zklistener.lost = True
                    zklistener.initial_connect = False

        while True:
            time.sleep(SLEEP_TIME)

    return canary
