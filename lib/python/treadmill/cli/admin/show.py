"""Trace treadmill application events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import heapq
import logging
import json
import zlib

import click

from treadmill import cli
from treadmill import context
from treadmill import zknamespace as z
from treadmill import zkutils

_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler"""

    @click.group()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--zookeeper', required=False,
                  envvar='TREADMILL_ZOOKEEPER',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    def top():
        """Show Treadmill apps.
        """

    @top.command()
    def scheduled():
        """List scheduled applications"""
        for app in sorted(context.GLOBAL.zk.conn.get_children(z.SCHEDULED)):
            cli.out(app)

    @top.command()
    def running():
        """List running applications"""
        for app in sorted(context.GLOBAL.zk.conn.get_children(z.RUNNING)):
            cli.out(app)

    @top.command()
    def pending():
        """List pending applications"""
        zkclient = context.GLOBAL.zk.conn

        data, _ = zkclient.get(z.PLACEMENT)
        if data:
            placement = json.loads(
                zlib.decompress(data).decode()
            )
        else:
            placement = []

        # App is pending if it's scheduled but has no placement.
        placed = {
            app for app, _before, _exp_before, after, _exp_after in placement
            if after
        }
        scheduled = set(zkclient.get_children(z.SCHEDULED))
        for app in sorted(scheduled - placed):
            cli.out(app)

    @top.command()
    def stopped():
        """List stopped applications"""
        running = set(context.GLOBAL.zk.conn.get_children(z.RUNNING))
        scheduled = set(context.GLOBAL.zk.conn.get_children(z.SCHEDULED))
        for app in sorted(running - scheduled):
            cli.out(app)

    @top.command()
    def endpoints():
        """Show endpoints and their status."""
        zkclient = context.GLOBAL.zk.conn
        discovery_state = zkclient.get_children(z.DISCOVERY_STATE)
        state = collections.defaultdict(dict)
        for hostname in discovery_state:
            state[hostname] = zkutils.get(
                zkclient,
                z.path.discovery_state(hostname)
            )

        discovery = zkclient.get_children(z.DISCOVERY)
        all_endpoints = []
        for hostname in discovery:
            endpoints = []
            for entry in zkutils.get(zkclient, z.path.discovery(hostname)):
                app, endpoint, proto, port = entry.split(':')
                port = int(port)
                endpoint_state = state[hostname].get(port)
                instance_pos = hostname.find('#')
                if instance_pos != -1:
                    hostport = '{}:{}'.format(hostname[:instance_pos], port)
                else:
                    hostport = '{}:{}'.format(hostname, port)

                endpoints.append(
                    (app, proto, endpoint, hostport, endpoint_state)
                )
            all_endpoints.append(endpoints)

        merged = heapq.merge(*all_endpoints)

        formatter = cli.make_formatter('endpoint')
        cli.out(formatter([
            {
                'name': name,
                'endpoint': endpoint,
                'proto': proto,
                'hostport': hostport,
                'state': state,
            } for name, proto, endpoint, hostport, state in merged
        ]))

    del stopped
    del pending
    del running
    del scheduled

    return top
