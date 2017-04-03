"""Treadmill trace CLI."""

from __future__ import absolute_import

import json
import logging
import socket
import sys
import urllib

import websocket as ws_client

import click

from treadmill import cli
from treadmill import context
from treadmill import restclient

from treadmill.apptrace import (events, printer)

_LOGGER = logging.getLogger(__name__)


class _RetryError(Exception):
    """Error indicating that retry attempt should be made."""

    def __init__(self, since):
        Exception.__init__(self)
        self.since = since


def _ws_events(ws_conn, app, snapshot, since):
    """Process websocket trace events."""

    last_timestamp = None
    try:
        ws_conn.send(json.dumps({'topic': '/trace',
                                 'filter': app,
                                 'since': since,
                                 'snapshot': snapshot}))

        trace_printer = printer.AppTracePrinter()
        while True:
            reply = ws_conn.recv()
            if not reply:
                break

            result = json.loads(reply)
            if '_error' in result:
                click.echo('Error: %s' % result['_error'], err=True)
                break

            event = events.AppTraceEvent.from_dict(result['event'])
            if event is None:
                break

            last_timestamp = event.timestamp
            trace_printer.process(event)
            if isinstance(event, events.DeletedTraceEvent):
                break

    except ws_client.WebSocketConnectionClosedException:
        _LOGGER.debug('ws connection closed, retrying.')
        raise _RetryError(last_timestamp)

    finally:
        ws_conn.close()


def _trace_loop(ctx, app, snapshot):
    """Instance trace loop."""
    ws_conn = None
    since = 0

    while True:
        apis = context.GLOBAL.ws_api(ctx['wsapi'])
        for api in apis:
            try:
                ws_conn = ws_client.create_connection(api)
                _LOGGER.debug('Using API %s', api)
                return _ws_events(ws_conn, app, snapshot, since)
            except socket.error:
                _LOGGER.debug('Connection failed, trying next: %s', api)
                continue
            except _RetryError as retry_err:
                since = retry_err.since

        if not ws_conn:
            click.echo('Could not connect to any Websocket APIs', err=True)
            sys.exit(-1)


def init():
    """Return top level command handler."""

    ctx = {}

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--api', required=False, help='REST API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_RESTAPI')
    @click.option('--wsapi', required=False, help='WebSocket API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_WSAPI')
    @click.option('--last', is_flag=True, default=False)
    @click.option('--snapshot', is_flag=True, default=False)
    @click.argument('app')
    def trace(api, wsapi, last, snapshot, app):
        """Trace application events.

        Invoking treadmill_trace with non existing application instance will
        cause the utility to wait for the specified instance to be started.

        Specifying already finished instance of the application will display
        historical trace information and exit status.

        Specifying only an application name will list all the instance IDs with
        trace information available.
        """
        # Disable too many branches.
        #
        # pylint: disable=R0912

        ctx['api'] = api
        ctx['wsapi'] = wsapi

        if '#' not in app:
            apis = context.GLOBAL.state_api(ctx['api'])
            url = '/trace/{app}'.format(
                app=urllib.quote(app)
            )

            try:
                response = restclient.get(apis, url)
                trace_info = response.json()

            except restclient.NotFoundError:
                trace_info = {
                    'name': app,
                    'instances': []
                }

            if not trace_info['instances']:
                print >> sys.stderr, '# Trace information does not exist.'
                return

            elif not last:
                for instanceid in sorted(trace_info['instances']):
                    cli.out(
                        '{app}#{instanceid}'.format(
                            app=trace_info['name'],
                            instanceid=instanceid
                        )
                    )
                return

            else:
                app = '{app}#{instanceid}'.format(
                    app=trace_info['name'],
                    instanceid=sorted(trace_info['instances'])[-1]
                )

        return _trace_loop(ctx, app, snapshot)

    return trace
