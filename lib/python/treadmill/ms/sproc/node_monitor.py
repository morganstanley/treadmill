"""Monitors for broken nodes and disables them proactively with alert.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time
import collections

import click
import six

from treadmill import context
from treadmill import presence
from treadmill import zknamespace as z
from treadmill import zkutils

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import alert

_LOGGER = logging.getLogger(__name__)

FACET = 'CONTAINER'


def _percentage_arg(arg):
    """create percentage"""
    if arg[-1] == '%':
        return float(arg.replace('%', '')) / 100.0
    raise Exception('Needs to be a percentage (i.e. 10%)')


def report_above_threshold(cell, partition,
                           broken_count, broken_limit):
    """Log and report above threshold broken count."""
    msg = ('{cell}/{partition}: broken node count above threshold -'
           ' {cur_nodes}/{max_nodes}').format(cell=cell,
                                              partition=partition,
                                              cur_nodes=broken_count,
                                              max_nodes=broken_limit)
    _LOGGER.critical('%s', msg)
    alert.send_event(
        event_type='cell.down-threshold',
        instanceid='{}/{}'.format(cell, partition),
        summary=msg,
        broken_node=broken_count,
        broken_limit=broken_limit
    )


def report_below_threshold(cell, partition,
                           broken_count, broken_limit):
    """Log and report below threshold broken count."""
    msg = ('{cell}/{partition}: broken node count below threshold -'
           ' {cur_nodes}/{max_nodes}').format(cell=cell,
                                              partition=partition,
                                              cur_nodes=broken_count,
                                              max_nodes=broken_limit)
    _LOGGER.info('%s', msg)
    alert.send_event(
        event_type='cell.down-threshold',
        instanceid='{}/{}'.format(cell, partition),
        summary=msg,
        broken_node=broken_count,
        broken_limit=broken_limit
    )


def _load_limits(zkclient):
    """Load threshold values for partitions"""
    limits = collections.defaultdict(int)

    partitions = zkclient.get_children(z.PARTITIONS)
    for part in partitions:
        data = zkutils.get(zkclient, z.path.partition(part))
        try:
            limits[part] = data['down-threshold']
        except KeyError:
            pass

    return limits


def _down_count(zkclient):
    """Count down servers per partition"""
    down = collections.defaultdict(int)

    servers = zkclient.get_children(z.SERVERS)
    up_servers = {presence.server_hostname(node)
                  for node in zkclient.get_children(z.SERVER_PRESENCE)}
    for server in servers:
        if server not in up_servers:
            data = zkutils.get(zkclient, z.path.server(server))
            down[data['partition']] += 1

    return down


def _monitor_loop(zkclient, cell, check_interval):
    """Main monitoring loop."""
    # TODO: make it simpler.
    #
    # R0912: Too many branches.
    # pylint: disable=R0912
    above_threshold = collections.defaultdict(bool)

    while True:

        limits = _load_limits(zkclient)
        down = _down_count(zkclient)

        for partition in limits:
            if down[partition] > limits[partition]:
                # Send alert once, and remember the state.
                if not above_threshold[partition]:
                    report_above_threshold(cell, partition,
                                           down[partition], limits[partition])
                above_threshold[partition] = True
            else:
                # Clear alert if it was set.
                if above_threshold[partition]:
                    report_below_threshold(cell, partition,
                                           down[partition], limits[partition])
                above_threshold[partition] = False

        # TODO: implement integrity checks.
        _LOGGER.info(
            'Partition down: %r',
            ['{}:{}'.format(key, val) for key, val in six.iteritems(down)]
        )

        # Sleep before next iteration - both when nodes exceed blackout
        # threshold or not.
        time.sleep(check_interval)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--check_interval', help='Interval between checks.',
                  type=int, default=60)
    def node_monitor(check_interval):
        """Monitors for broken nodes and disables them with alert."""

        zkclient = context.GLOBAL.zk.conn
        zkclient.add_listener(zkutils.exit_on_disconnect)

        lock = zkutils.make_lock(zkclient, z.path.election(__name__))
        _LOGGER.info('Waiting for leader lock.')

        with lock:
            _LOGGER.info('Running.')

            while not zkclient.exists(z.BLACKEDOUT_SERVERS):
                _LOGGER.warning(
                    '%r node not created yet. Cell masters running?',
                    z.BLACKEDOUT_SERVERS
                )
                time.sleep(30)

            _monitor_loop(zkclient, context.GLOBAL.cell,
                          check_interval)

    return node_monitor
