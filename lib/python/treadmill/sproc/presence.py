"""Runs Treadmill application presence daemon.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import signal
import sys
import time
import traceback

import click

from treadmill import appenv
from treadmill import appevents
from treadmill import context
from treadmill import exc
from treadmill import presence
from treadmill import subproc
from treadmill import supervisor
from treadmill import tickets
from treadmill import utils
from treadmill import zkutils

from treadmill.appcfg import abort as app_abort
from treadmill.appcfg import manifest as app_manifest

from treadmill.apptrace import events as traceevents


_LOGGER = logging.getLogger(__name__)

#: 3 hours
_TICKETS_REFRESH_INTERVAL = 60 * 60 * 3


def _start_service_sup(tm_env, manifest, container_dir):
    """Safely start services supervisor."""
    for service in manifest['services']:
        if service['trace']:
            appevents.post(
                tm_env.app_events_dir,
                traceevents.ServiceRunningTraceEvent(
                    instanceid=manifest['name'],
                    uniqueid=manifest['uniqueid'],
                    service=service['name']
                )
            )

    try:
        supervisor.control_service(
            os.path.join(container_dir, 'sys', 'start_container'),
            supervisor.ServiceControlAction.once
        )
    except subproc.CalledProcessError:
        raise exc.ContainerSetupError('start_container')


def _get_tickets(manifest, container_dir):
    """Get tickets."""
    principals = set(manifest.get('tickets', []))
    if not principals:
        return False

    tkts_spool_dir = os.path.join(
        container_dir, 'root', 'var', 'spool', 'tickets')

    tickets.request_tickets(
        context.GLOBAL.zk.conn,
        manifest['name'],
        tkts_spool_dir,
        principals
    )

    # Check that all requested tickets are valid.
    for princ in principals:
        krbcc_file = os.path.join(tkts_spool_dir, princ)
        if not tickets.krbcc_ok(krbcc_file):
            _LOGGER.error('Missing or expired tickets: %s, %s',
                          princ, krbcc_file)
            raise exc.ContainerSetupError(princ,
                                          app_abort.AbortedReason.TICKETS)
        else:
            _LOGGER.info('Ticket ok: %s, %s', princ, krbcc_file)

    return True


def _refresh_tickets(manifest, container_dir):
    """Refreshes the tickets with the given frequency."""
    tkts_spool_dir = os.path.join(container_dir, 'root', 'var', 'spool',
                                  'tickets')

    principals = set(manifest.get('tickets', []))
    tickets.request_tickets(context.GLOBAL.zk.conn,
                            manifest['name'],
                            tkts_spool_dir,
                            principals)


def sigterm_handler(_signo, _stack_frame):
    """Will raise SystemExit exception and allow for cleanup."""
    _LOGGER.info('Got term signal.')
    sys.exit(0)


def init():
    """App main."""

    @click.group(name='presence')
    def presence_grp():
        """Register container/app presence."""
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)

    @presence_grp.command(name='register')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--refresh-interval', type=int,
                  default=_TICKETS_REFRESH_INTERVAL)
    @click.argument('manifest', type=click.Path(exists=True))
    @click.argument('container-dir', type=click.Path(exists=True))
    def register_cmd(approot, refresh_interval, manifest, container_dir):
        """Register container presence."""
        try:
            _LOGGER.info('Configuring sigterm handler.')
            signal.signal(utils.term_signal(), sigterm_handler)

            tm_env = appenv.AppEnvironment(approot)
            app = app_manifest.read(manifest)

            app_presence = presence.EndpointPresence(
                context.GLOBAL.zk.conn,
                app
            )

            # If tickets are not ok, app will be aborted.
            #
            # If tickets acquired successfully, services will start, and
            # tickets will be refreshed after each interval.
            refresh = False
            try:
                app_presence.register()
                refresh = _get_tickets(app, container_dir)
                _start_service_sup(tm_env, app, container_dir)
            except exc.ContainerSetupError as err:
                app_abort.abort(
                    container_dir,
                    why=err.reason,
                    payload=traceback.format_exc()
                )

            while True:
                # Need to sleep anyway even if not refreshing tickets.
                time.sleep(refresh_interval)
                if refresh:
                    _refresh_tickets(app, container_dir)
        finally:
            _LOGGER.info('Stopping zookeeper.')
            context.GLOBAL.zk.conn.stop()

    del register_cmd
    return presence_grp
