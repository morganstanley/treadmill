"""Treadmill trace CLI.
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import logging
import sys

import click

from six.moves import urllib_parse

from treadmill import cli
from treadmill import context
from treadmill import restclient
from treadmill.websocket import client as ws_client

from treadmill.trace.app import (events, printer)

_LOGGER = logging.getLogger(__name__)


_RC_DEFAULT_EXIT = 100

_RC_ABORTED = 101

_RC_KILLED = 102

_RC_NO_TRACES = 103


def _trace_loop(app, snapshot):
    """Instance trace loop."""

    trace_printer = printer.AppTracePrinter()

    rc = {'rc': _RC_DEFAULT_EXIT}

    if not snapshot:
        click.echo(
            '# No trace information yet, waiting...\r', nl=False, err=True
        )

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
            context.GLOBAL.ws_api(),
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

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--last', is_flag=True, default=False)
    @click.option('--snapshot', is_flag=True, default=False)
    @click.argument('app')
    def trace(last, snapshot, app):
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
            103 - no trace information
            100 - everything else.
        """
        # Disable too many branches.
        #
        # pylint: disable=R0912

        if '#' not in app:
            apis = context.GLOBAL.state_api()
            url = '/state/?finished=1&match={app}'.format(
                app=urllib_parse.quote(app)
            )

            try:
                response = restclient.get(apis, url)
                app_states = response.json()

            except restclient.NotFoundError:
                app_states = []

            if not app_states:
                click.echo('# Trace information does not exist.', err=True)
                sys.exit(_RC_NO_TRACES)

            elif not last:
                for name in [app['name'] for app in app_states]:
                    cli.out(name)
                return None

            else:
                app = app_states[-1]['name']

        return _trace_loop(app, snapshot)

    return trace
