"""Trace treadmill application events."""


import sys

import click

from treadmill import context

from treadmill import cli
from treadmill.apptrace import (zk, printer)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--last', is_flag=True, default=False)
    @click.option('--snapshot', is_flag=True, default=False)
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
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
            tasks = zk.list_history(context.GLOBAL.zk.conn, app)
            if not tasks:
                print('# Trace information does not exist.', file=sys.stderr)
                return

            elif not last:
                for task in sorted(tasks):
                    print(task)
                return

            else:
                task = sorted(tasks)[-1]

        else:
            task = app

        trace = zk.AppTrace(
            context.GLOBAL.zk.conn,
            task,
            callback=printer.AppTracePrinter()
        )

        trace.run(snapshot=snapshot)
        try:
            while not trace.wait(timeout=1):
                pass

        except KeyboardInterrupt:
            pass

    return trace
