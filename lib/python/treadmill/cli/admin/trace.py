"""Trace treadmill application events.
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import click

from treadmill import context

from treadmill import cli
from treadmill.trace.app import (zk, printer)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--last', is_flag=True, default=False)
    @click.option('--snapshot', is_flag=True, default=False)
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--zookeeper', required=False,
                  envvar='TREADMILL_ZOOKEEPER',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.argument('app')
    def trace(last, snapshot, app):
        """Trace application events.

        Invoking treadmill_trace with non existing application instance will
        cause the utility to wait for the specified instance to be started.

        Specifying already finished instance of the application will display
        historical trace information and exit status.
        """
        if '#' not in app:
            # Instance is not specified, list matching and exit.
            traces = zk.list_traces(context.GLOBAL.zk.conn, app)
            if not traces:
                click.echo('# Trace information does not exist.', err=True)
                return

            elif not last:
                for instance_id in traces:
                    cli.out(instance_id)
                return

            else:
                instance_id = traces[-1]

        else:
            instance_id = app

        trace = zk.AppTraceLoop(
            context.GLOBAL.zk.conn,
            instance_id,
            event_handler=printer.AppTracePrinter()
        )

        trace.run(snapshot=snapshot)
        try:
            while not trace.wait(timeout=1):
                pass

        except KeyboardInterrupt:
            pass

    return trace
