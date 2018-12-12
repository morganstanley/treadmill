"""Waits for Treadmill application completion.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import sys

import click

from treadmill import cli
from treadmill import context
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import yamlwrapper as yaml

from treadmill.trace.app import (events, zk)

_LOGGER = logging.getLogger(__name__)


def print_yaml(obj):
    """Print yaml wih correct options."""
    cli.out(yaml.dump(obj,
                      default_flow_style=False,
                      explicit_start=True,
                      explicit_end=True))


class _AppTraceEventsOnly(events.AppTraceEventHandler):
    """Handler used to integrate trace events into final state of the container
    """

    def on_scheduled(self, when, instanceid, server, why):
        """Invoked when task is scheduled.
        """

    def on_pending(self, when, instanceid, why):
        """Invoked when task is pending.
        """

    def on_pending_delete(self, when, instanceid, why):
        """Invoked when task is about to be deleted.
        """

    def on_configured(self, when, instanceid, server, uniqueid):
        """Invoked when task is configured.
        """

    def on_deleted(self, when, instanceid):
        """Invoked when task is deleted.
        """

    def on_finished(self, when, instanceid, server, signal, exitcode):
        """Invoked when task is finished."""
        if exitcode > 255:
            cli.out(
                '%s - %s killed, signal: %s',
                utils.strftime_utc(when),
                instanceid,
                utils.signal2name(signal)
            )
            self.ctx.update(
                {
                    'signal': signal,
                    'when': when,
                    'server': server
                }
            )
        else:
            cli.out(
                '%s - %s exited, return code: %s',
                utils.strftime_utc(when),
                instanceid,
                exitcode
            )
            self.ctx.update(
                {
                    'exitcode': exitcode,
                    'when': when,
                    'server': server
                }
            )

    def on_killed(self, when, instanceid, server, is_oom):
        """Default task-finished handler.
        """

    def on_aborted(self, when, instanceid, server, why):
        """Invoked when task is aborted.
        """

    def on_service_running(self, when, instanceid, server, uniqueid, service):
        """Invoked when service is running.
        """

    def on_service_exited(self, when, instanceid, server, uniqueid, service,
                          exitcode, signal):
        """Suppress stdout/err info."""
        if exitcode > 255:
            cli.out(
                '%s - %s/%s/service/%s killed, signal: %s',
                utils.strftime_utc(when),
                instanceid,
                uniqueid,
                service,
                utils.signal2name(signal)
            )
        else:
            cli.out(
                '%s - %s/%s/service/%s exited, return code: %s',
                utils.strftime_utc(when),
                instanceid,
                uniqueid,
                service,
                exitcode
            )


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
        expected_nb = len(instances)
        finished = []

        zkclient = context.GLOBAL.zk.conn
        done_event = zkclient.handler.event_object()
        callback = _AppTraceEventsOnly()

        def _make_watch(instance):
            """Make watch function, closure on zkclient, cell and instance."""

            info = dict(instance=instance)

            @utils.exit_on_unhandled
            def _watch_scheduled(data, _stat, event):
                """Watch on scheduled node."""

                if data is None and event is None:
                    # ZNode is not there yet
                    _LOGGER.info('Waiting for %r', instance)
                    return True

                elif event is not None and event.type == 'DELETED':

                    trace = zk.AppTrace(zkclient, instance, callback)
                    trace.run(snapshot=True, ctx=info)

                    print_yaml(info)

                    finished.append(info)
                    if len(finished) == expected_nb:
                        done_event.set()
                    return False

                else:
                    # ZNode is here, waiting for instance to terminate.
                    return True

            return _watch_scheduled

        for instance in instances:
            # Setup a datawatch on each of the instance's scheduled path
            path_scheduled = z.path.scheduled(instance)
            zkclient.DataWatch(path_scheduled)(
                _make_watch(instance)
            )

        rc = None
        try:
            while not done_event.wait(timeout=1):
                pass
        except KeyboardInterrupt:
            done_event.set()
            rc = -1

        finally:
            zkclient.stop()

        if rc is None:
            # Check for success
            rc = 0
            for info in finished:
                if 'exitcode' in info and info['exitcode'] == 0:
                    _LOGGER.info('%s: ok', info['instance'])
                else:
                    _LOGGER.info('%s: failure', info['instance'])
                    rc = 1

        sys.exit(rc)

    return wait
