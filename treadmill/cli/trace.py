"""Treadmill trace CLI.
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import logging
import urllib.request
import urllib.parse
import urllib.error
import sys

import click

from treadmill import cli
from treadmill import context
from treadmill import restclient
from treadmill.websocket import client as ws_client

from treadmill.apptrace import (events, printer)

_LOGGER = logging.getLogger(__name__)


_RC_DEFAULT_EXIT = 100

_RC_ABORTED = 101

_RC_KILLED = 102


def _trace_loop(ctx, app, snapshot):
    """Instance trace loop."""

    trace_printer = printer.AppTracePrinter()

    rc = {'rc': _RC_DEFAULT_EXIT}

    def on_message(result):
        """Callback to process trace message."""
        _LOGGER.debug('result: %r', result)
        event = events.AppTraceEvent.from_dict(result['event'])
        if event is None:
            return False

        trace_printer.process(event)

        if isinstance(event, events.FinishedTraceEvent):
            rc['rc'] = event.rc

        if isinstance(event, events.KilledTraceEvent):
            rc['rc'] = _RC_KILLED

        if isinstance(event, events.AbortedTraceEvent):
            rc['rc'] = _RC_ABORTED

        if isinstance(event, events.DeletedTraceEvent):
            return False

        return True

    def on_error(result):
        """Callback to process errors."""
        click.echo('Error: %s' % result['_error'], err=True)

    try:
        ws_client.ws_loop(
            ctx['wsapi'],
            {'topic': '/trace',
             'filter': app},
            snapshot,
            on_message,
            on_error
        )

        sys.exit(rc['rc'])

    except ws_client.WSConnectionError:
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

        The trace will exit with the exit code of the container service that
        caused container finish (reached retry count).

        Special error codes if service did not exit gracefully and it is not
        possible to capture the return code:

            101 - container was aborted.
            102 - container was killed (possible out of memory)
            100 - everything else.
        """
        # Disable too many branches.
        #
        # pylint: disable=R0912
        ctx['api'] = api
        ctx['wsapi'] = wsapi

        if '#' not in app:
            apis = context.GLOBAL.state_api(ctx['api'])
            url = '/state/?finished=1&match={app}'.format(
                app=urllib.parse.quote(app)
            )

            try:
                response = restclient.get(apis, url)
                app_states = response.json()

            except restclient.NotFoundError:
                app_states = []

            if not app_states:
                click.echo('# Trace information does not exist.', err=True)
                return

            elif not last:
                for name in [app['name'] for app in app_states]:
                    cli.out(name)
                return

            else:
                app = app_states[-1]['name']

        return _trace_loop(ctx, app, snapshot)

    return trace
