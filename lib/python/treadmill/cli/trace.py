"""Treadmill trace CLI."""

from __future__ import absolute_import

import logging
import sys
import urllib

import click

from treadmill import cli
from treadmill import context
from treadmill import restclient
from treadmill.websocket import client as ws_client

from treadmill.apptrace import (events, printer)

_LOGGER = logging.getLogger(__name__)


def _trace_loop(ctx, app, snapshot):
    """Instance trace loop."""
    trace_printer = printer.AppTracePrinter()

    def on_message(result):
        """Callback to process trace message."""
        event = events.AppTraceEvent.from_dict(result['event'])
        if event is None:
            return False

        trace_printer.process(event)
        if isinstance(event, events.DeletedTraceEvent):
            return False

        return True

    def on_error(result):
        """Callback to process errors."""
        click.echo('Error: %s' % result['_error'], err=True)

    try:
        return ws_client.ws_loop(
            ctx['wsapi'],
            {'topic': '/trace',
             'filter': app},
            snapshot,
            on_message,
            on_error
        )
    except ws_client.ConnectionError:
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
