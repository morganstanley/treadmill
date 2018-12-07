"""Treadmill server trace CLI.
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import logging
import sys

import click

from treadmill import cli
from treadmill import context
from treadmill.websocket import client as ws_client

from treadmill.trace.server import (events, printer)

_LOGGER = logging.getLogger(__name__)


def _trace_loop(server, snapshot):
    """Server trace loop."""

    trace_printer = printer.ServerTracePrinter()

    if not snapshot:
        click.echo(
            '# No trace information yet, waiting...\r', nl=False, err=True
        )

    def on_message(result):
        """Callback to process trace message."""
        _LOGGER.debug('result: %r', result)
        event = events.ServerTraceEvent.from_dict(result['event'])
        if event is None:
            return False

        trace_printer.process(event)

        return True

    def on_error(result):
        """Callback to process errors."""
        click.echo('Error: %s' % result['_error'], err=True)

    try:
        ws_client.ws_loop(
            context.GLOBAL.ws_api(),
            {'topic': '/server-trace',
             'filter': server},
            snapshot,
            on_message,
            on_error
        )
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
    @click.option('--snapshot', is_flag=True, default=False)
    @click.argument('server')
    def trace(snapshot, server):
        """Trace server events."""
        return _trace_loop(server, snapshot)

    return trace
