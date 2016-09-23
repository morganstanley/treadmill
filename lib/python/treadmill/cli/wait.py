"""Waits for Treadmill application completion."""
from __future__ import absolute_import

import sys

import logging
import threading

import click
import kazoo
import yaml

from .. import apptrace
from .. import context
from .. import exc
from .. import utils
from .. import zknamespace as z

from treadmill import cli


def print_yaml(obj):
    """Print yaml wih correct options."""
    print yaml.dump(obj,
                    default_flow_style=False,
                    explicit_start=True,
                    explicit_end=True)


class AppTraceEventsOnly(apptrace.AppTraceEventsStdout):
    """Prints app events without stdout/err info."""

    def __init__(self):
        apptrace.AppTraceEventsStdout.__init__(self)

    def on_service_exited(self, when, service, svcinfo):
        """Suppress stdout/err info."""
        if svcinfo.rc == 255:
            print '# %s - service %s [ %s ] killed, oom: %s, signal: %s' % (
                utils.strftime_utc(when),
                service,
                svcinfo.hostname,
                svcinfo.oom,
                apptrace.signal2name(svcinfo.sig))
        else:
            print '# %s - service %s [ %s ] exited, oom: %s, rc: %s' % (
                utils.strftime_utc(when),
                service,
                svcinfo.hostname,
                svcinfo.oom,
                svcinfo.rc)


def init():
    """Top level command handler."""
    # too many branches.
    #
    # pylint: disable=R0912

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.argument('instances', nargs=-1)
    def wait(instances):
        """Wait for all instances to exit."""
        waitinglist = list(instances)
        finished = []

        done_event = threading.Event()
        callback = AppTraceEventsOnly()

        def _make_watch(zkclient, instance):
            """Make watch function, closure on zkclient, cell and instance."""

            @exc.exit_on_unhandled
            def _watch_scheduled(data, stat, _event):
                """Watch on scheduled node."""
                if data is None and stat is None:

                    trace = apptrace.AppTrace(zkclient, instance, callback)
                    trace.run(snapshot=True)
                    info = apptrace.app_state(trace.exitinfo)
                    info['instance'] = instance
                    print_yaml(info)

                    finished.append(info)
                    if len(finished) == len(waitinglist):
                        done_event.set()
                    return False
                else:
                    return True

            return _watch_scheduled

        for instance in instances:
            path_scheduled = z.path.scheduled(instance)
            datawatch = kazoo.recipe.watchers.DataWatch(context.GLOBAL.zk.conn,
                                                        path_scheduled)
            datawatch(_make_watch(context.GLOBAL.zk.conn, instance))

        done_event.wait()

        # Check for success
        rc = 0
        for info in finished:
            if 'exit_code' in info and info['exit_code'] == 0:
                logging.info('%s: ok', info['instance'])
            else:
                logging.info('%s: failure', info['instance'])
                rc = 1

        sys.exit(rc)

    return wait
