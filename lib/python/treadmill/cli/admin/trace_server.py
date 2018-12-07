"""Trace treadmill server events.
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import click

from treadmill import context

from treadmill import cli
from treadmill.trace.server import (zk, printer)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--snapshot', is_flag=True, default=False)
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--zookeeper', required=False,
                  envvar='TREADMILL_ZOOKEEPER',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.argument('server')
    def trace(snapshot, server):
        """Trace server events."""
        trace = zk.ServerTraceLoop(
            context.GLOBAL.zk.conn,
            server,
            event_handler=printer.ServerTracePrinter()
        )

        trace.run(snapshot=snapshot)
        try:
            while not trace.wait(timeout=1):
                pass

        except KeyboardInterrupt:
            pass

    return trace
