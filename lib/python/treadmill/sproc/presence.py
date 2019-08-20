"""Runs Treadmill application register daemon.
"""

# TODO: it no longer registers anything, just refreshes tickets. Need to
#       rename.

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

from treadmill import context
from treadmill import exc
from treadmill import keytabs
from treadmill import subproc
from treadmill import supervisor
from treadmill import tickets
from treadmill import utils
from treadmill import zkutils

from treadmill.keytabs2 import client as kt_client
from treadmill.appcfg import abort as app_abort
from treadmill.appcfg import manifest as app_manifest

_LOGGER = logging.getLogger(__name__)

#: 3 hours
_TICKETS_REFRESH_INTERVAL = 60 * 60 * 3


def _start_service_sup(container_dir):
    """Safely start services supervisor."""
    try:
        supervisor.control_service(
            os.path.join(container_dir, 'sys', 'start_container'),
            supervisor.ServiceControlAction.once
        )
    except subproc.CalledProcessError:
        raise exc.ContainerSetupError('start_container')


def _get_keytabs(manifest, container_dir, locker_pattern):
    """Get keytabs."""
    # keytab of 'proid:service' is not fetched from keytab locker
    keytabs_to_fetch = set()
    kt_specs = set()
    for kt in manifest.get('keytabs', []):
        if ':' not in kt:
            keytabs_to_fetch.add(kt)
        else:
            kt_specs.add(kt)

    _LOGGER.debug('keytabs to fetch from locker: %r', keytabs_to_fetch)
    if not keytabs_to_fetch:
        return

    kts_spool_dir = os.path.join(
        container_dir, 'root', 'var', 'spool', 'keytabs')

    try:
        kt_client.request_keytabs(
            context.GLOBAL.zk.conn,
            manifest['name'],
            kts_spool_dir,
            locker_pattern,
        )
    except Exception:
        _LOGGER.exception('Exception processing keytabs.')
        raise exc.ContainerSetupError('Get keytabs error',
                                      app_abort.AbortedReason.KEYTABS)

    # add fetched host keytabs to /etc/krb5.keytab
    kt_dest = os.path.join(container_dir, 'overlay', 'etc', 'krb5.keytab')
    keytabs.add_keytabs_to_file(kts_spool_dir, 'host', kt_dest)

    # add fetched keytabs to keytab spec file
    for kt_spec in kt_specs:
        owner, princ = kt_spec.split(':', 1)
        kt_dest = os.path.join(kts_spool_dir, owner)
        keytabs.add_keytabs_to_file(kts_spool_dir, princ, kt_dest, owner)


def _get_tickets(manifest, container_dir):
    """Get tickets."""
    principals = set(manifest.get('tickets', []))
    if not principals:
        return False

    tkts_spool_dir = os.path.join(
        container_dir, 'root', 'var', 'spool', 'tickets')

    try:
        tickets.request_tickets(
            context.GLOBAL.zk.conn,
            manifest['name'],
            tkts_spool_dir,
            principals
        )
    except Exception:
        _LOGGER.exception('Exception processing tickets.')
        raise exc.ContainerSetupError('Get tickets error',
                                      app_abort.AbortedReason.TICKETS)

    # Check that all requested tickets are valid.
    for princ in principals:
        krbcc_file = os.path.join(tkts_spool_dir, princ)
        if not tickets.krbcc_ok(krbcc_file):
            _LOGGER.error('Missing or expired tickets: %s, %s',
                          princ, krbcc_file)
            raise exc.ContainerSetupError(princ,
                                          app_abort.AbortedReason.TICKETS)
        _LOGGER.info('Ticket ok: %s, %s', princ, krbcc_file)

    return True


def _refresh_tickets(manifest, container_dir):
    """Refreshes the tickets with the given frequency."""
    tkts_spool_dir = os.path.join(container_dir, 'root', 'var', 'spool',
                                  'tickets')

    # we do not abort here as we will make service fetch ticket again
    # after register service is started again
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
    @click.option('--refresh-interval', type=int,
                  default=_TICKETS_REFRESH_INTERVAL)
    @click.option('--kt-locker-pattern', required=True,
                  help='kt locker discovery pattern')
    @click.argument('manifest', type=click.Path(exists=True))
    @click.argument('container-dir', type=click.Path(exists=True))
    def register_cmd(refresh_interval, kt_locker_pattern,
                     manifest, container_dir):
        """Register container presence."""
        try:
            _LOGGER.info('Configuring sigterm handler.')
            signal.signal(utils.term_signal(), sigterm_handler)

            app = app_manifest.read(manifest)

            # If tickets are not ok, app will be aborted.
            #
            # If tickets acquired successfully, services will start, and
            # tickets will be refreshed after each interval.
            refresh = False
            try:
                refresh = _get_tickets(app, container_dir)
                _get_keytabs(app, container_dir, kt_locker_pattern)
                _start_service_sup(container_dir)
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
