"""Treadmill discovery CLI.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import socket
import sys

import click

from treadmill import cli
from treadmill import context
from treadmill.websocket import client as ws_client


_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--check-state', is_flag=True, default=False)
    @click.option('--watch', is_flag=True, default=False)
    @click.option('--separator', default=' ')
    @click.argument('app')
    @click.argument('endpoint', required=False, default='*:*')
    def discovery(check_state, watch, separator, app, endpoint):
        """Show state of scheduled applications."""
        if ':' not in endpoint:
            endpoint = '*:' + endpoint

        proto, endpoint_name = endpoint.split(':')

        def on_message(result):
            """Callback to process trace message."""
            instance = ':'.join([
                result['name'], result['proto'], result['endpoint']
            ])
            host = result['host']
            port = result['port']
            hostport = '%s:%s' % (host, port)
            if host is not None:
                record = [instance, hostport]
                if check_state:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)

                    try:
                        sock.connect((host, int(port)))
                        sock.close()
                        state = 'up'
                    except socket.error:
                        state = 'down'

                    record.append(state)

                output = separator.join(record)
            else:
                output = instance

            cli.out(output)
            return True

        def on_error(result):
            """Callback to process errors."""
            click.echo('Error: %s' % result['_error'], err=True)

        try:
            return ws_client.ws_loop(
                context.GLOBAL.ws_api(),
                {'topic': '/endpoints',
                 'filter': app,
                 'proto': proto,
                 'endpoint': endpoint_name},
                not watch,
                on_message,
                on_error
            )
        except ws_client.WSConnectionError:
            click.echo('Could not connect to any Websocket APIs', err=True)
            sys.exit(-1)

    return discovery
