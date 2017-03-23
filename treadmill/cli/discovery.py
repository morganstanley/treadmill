"""Treadmill discovery CLI."""


import json
import logging
import socket
import sys

import websocket as ws_client

import click

from .. import cli
from treadmill import context


_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""

    ctx = {}

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--api', required=False, help='API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_WSAPI')
    @click.option('--check-state', is_flag=True, default=False)
    @click.option('--watch', is_flag=True, default=False)
    @click.option('--separator', default=' ')
    @click.argument('app')
    @click.argument('endpoint', required=False, default='*')
    def discovery(api, check_state, watch, separator, app, endpoint):
        """Show state of scheduled applications."""
        ctx['api'] = api
        apis = context.GLOBAL.ws_api(ctx['api'])

        ws = None
        for api in apis:
            try:
                ws = ws_client.create_connection(api)
                _LOGGER.debug('Using API %s', api)
                break
            except socket.error:
                _LOGGER.debug('Could not connect to %s, trying next SRV '
                              'record', api)
                continue

        if not ws:
            click.echo('Could not connect to any Websocket APIs')
            sys.exit(-1)

        ws.send(json.dumps({'topic': '/endpoints',
                            'filter': app,
                            'proto': 'tcp',
                            'endpoint': endpoint,
                            'snapshot': not watch}))
        while True:
            reply = ws.recv()
            if not reply:
                break
            result = json.loads(reply)
            if '_error' in result:
                click.echo('Error: %s' % result['_error'], err=True)
                break

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

            print(output)

        ws.close()

    return discovery
