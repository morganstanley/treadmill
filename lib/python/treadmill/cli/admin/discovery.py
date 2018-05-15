"""Trace treadmill application events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import socket
import sys

import click

from treadmill import context
from treadmill import discovery

from treadmill import cli


_LOGGER = logging.getLogger()


def _iterate(discovery_iter, check_state, sep):
    """Iterate and output discovered endpoints."""
    for (app, hostport) in discovery_iter:
        if hostport:
            state = ''
            if check_state:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)

                try:
                    host, port = hostport.split(':')
                    sock.connect((host, int(port)))
                    sock.close()
                    state = 'up'
                except socket.error:
                    state = 'down'

            record = [app, hostport]
            if state:
                record.append(state)
            output = sep.join(record)
        else:
            output = app

        print(output.strip())
        sys.stdout.flush()


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--zookeeper', required=False,
                  envvar='TREADMILL_ZOOKEEPER',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--watch', is_flag=True, default=False)
    @click.option('--check-state', is_flag=True, default=False)
    @click.option('--separator', default=' ')
    @click.argument('app')
    @click.argument('endpoint', required=False)
    def top(watch, check_state, separator, app, endpoint):
        """Discover container endpoints."""
        if not endpoint:
            endpoint = '*'

        discovery_iter = discovery.iterator(
            context.GLOBAL.zk.conn, app, endpoint, watch)
        _iterate(discovery_iter, check_state, separator)

    return top
