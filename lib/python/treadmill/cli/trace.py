"""Trace treadmill application events."""
from __future__ import absolute_import

import sys

import click

from .. import apptrace
from .. import context
from .. import utils

from treadmill import cli


class _AppTrace(apptrace.AppTraceEvents):
    """Base class for processing events."""

    def on_task_scheduled(self, when, server):
        """Invoked when task is scheduled."""
        print '%s - task scheduled on %s' % (utils.strftime_utc(when), server)

    def on_task_pending(self, when):
        """Invoked when task is pending."""
        print '%s - task is pending' % (utils.strftime_utc(when))

    def on_task_deleted(self, when):
        """Invoked when task is deleted."""
        print '%s - task is deleted' % (utils.strftime_utc(when))

    def on_task_finished(self, when, server):
        """Invoked when task is finished."""
        print '%s - task finished on %s' % (utils.strftime_utc(when), server)

    def on_task_killed(self, when, server, oom):
        """Default task-finished handler."""
        if oom:
            print '%s - task killed, out of memory' % utils.strftime_utc(when)
        else:
            print '%s - task killed' % (utils.strftime_utc(when))

    def on_task_aborted(self, when, server):
        """Invoked when task is aborted"""
        print '%s - aborted: %s.' % (utils.strftime_utc(when), server)

    def on_service_running(self, when, server, service):
        """Invoked when service is running."""
        print '%s - service [%s] is running' % (utils.strftime_utc(when),
                                                service)

    def on_service_exit(self, when, server, service, exitcode, signal):
        """Invoked when service exits."""
        if exitcode == 255:
            print '%s - service [%s] killed, signal: %s' % (
                utils.strftime_utc(when), service, utils.signal2name(signal))
        else:
            print '%s - service [%s] exited, return code: %s' % (
                utils.strftime_utc(when), service, exitcode)


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

        The treadmill_trace utility will exit with the same exit code/signal as
        the last exited service inside the Treadmill application container.
        """
        if app.find('#') == -1:
            # Instance is not specified, list matching and exit.
            tasks = apptrace.list_history(context.GLOBAL.zk.conn, app)
            if not last:
                for task in sorted(tasks):
                    print task
                return
            else:
                if tasks:
                    task = tasks[-1]
                else:
                    print >> sys.stderr, '# Task does not exist.'
                    return
        else:
            task = app

        print task
        print

        callback = _AppTrace()
        trace = apptrace.AppTrace(context.GLOBAL.zk.conn, task, callback)
        trace.run(snapshot=snapshot)

        try:
            while not trace.wait(1):
                pass

        except KeyboardInterrupt:
            pass

    return trace
