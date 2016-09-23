"""Runs Treadmill application presence daemon."""
from __future__ import absolute_import

import time
import logging
import os

import click
import yaml

from .. import presence
from .. import context
from .. import subproc
from .. import supervisor
from .. import tickets
from .. import zkutils


_LOGGER = logging.getLogger(__name__)

#: 3 hours
_TICKETS_REFRESH_INTERVAL = 60 * 60 * 3


def _start_service_sup(container_dir):
    """Safely start services supervisor."""
    sys_dir = os.path.join(container_dir, 'sys')
    svc_sup_dir = os.path.join(sys_dir, 'start_container')

    if not os.path.exists(os.path.join(svc_sup_dir, 'self.pid')):
        supervisor.start_service(sys_dir, 'start_container', once=True)
    else:
        _LOGGER.info('services supervisor already started.')


def init():
    """App main."""

    @click.group(name='presence')
    def presence_grp():
        """Register container/app presence."""
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)

    @presence_grp.command()
    @click.option('--refresh-interval', type=int,
                  default=_TICKETS_REFRESH_INTERVAL)
    @click.argument('manifest', type=click.File('rb'))
    @click.argument('container-dir', type=click.Path(exists=True))
    @click.argument('appevents-dir', type=click.Path(exists=True))
    def register(refresh_interval, manifest, container_dir, appevents_dir):
        """Register container presence."""
        del appevents_dir

        app = yaml.load(manifest.read())
        appname = app['name']
        app_presence = presence.EndpointPresence(context.GLOBAL.zk.conn,
                                                 app)
        app_presence.register()

        tkts_spool_dir = os.path.join(
            container_dir, 'root', 'var', 'spool', 'tickets')

        reply = tickets.request_tickets(context.GLOBAL.zk.conn, appname)
        if reply:
            tickets.store_tickets(reply, tkts_spool_dir)
        else:
            logging.error('Error requesting tickets.')

        _start_service_sup(container_dir)

        while True:
            time.sleep(refresh_interval)
            reply = tickets.request_tickets(context.GLOBAL.zk.conn, appname)
            if reply:
                tickets.store_tickets(reply, tkts_spool_dir)
            else:
                logging.error('Error requesting tickets.')

    @presence_grp.command()
    @click.argument('manifest', type=click.File('rb'))
    @click.argument('container-dir', type=click.Path(exists=True))
    @click.argument('appevents-dir', type=click.Path(exists=True))
    def monitor(manifest, container_dir, appevents_dir):
        """Monitor container services."""
        app = yaml.load(manifest.read())
        svc_presence = presence.ServicePresence(
            app,
            container_dir,
            appevents_dir,
        )

        sys_dir = os.path.join(container_dir, 'sys')
        svc_sup_dir = os.path.join(sys_dir, 'start_container')

        failed_svc = None
        killed = False

        # Check that start_container was not terminated. This fixed race
        # condition if the presence exits and while restarted, start_container
        # is terminated.
        svc_sup_ran_once = os.path.exists(os.path.join(svc_sup_dir,
                                                       'self.pid'))
        _LOGGER.info('services supervisor ran once: %s', svc_sup_ran_once)
        svc_sup_down = presence.is_down(svc_sup_dir)
        _LOGGER.info('services supervisor down: %s', svc_sup_down)
        if svc_sup_down and svc_sup_ran_once:
            _LOGGER.info('services supervisor was terminated, exiting.')
        else:
            svc_presence.ensure_supervisors_running()

            # Try to start the service, taking into account number of restarts.
            # If the number of restarts is more than specified, delete app from
            # the model, which will trigger container shutdown.
            #
            # In case of container shutdown (application evicted from the
            # server), exit_app will not be called.
            while True:
                success, failed_svc = svc_presence.start_all()
                if not success:
                    break

                svc_presence.wait_for_exit(svc_sup_dir)
                if presence.is_down(svc_sup_dir):
                    _LOGGER.info('Container services supervisor is down.')
                    failed_svc = None
                    killed = True
                    break

        svc_presence.exit_app(failed_svc, killed=killed)

        _LOGGER.info('Shutting down sys supervisor.')
        subproc.call(['s6-svscanctl', '-pi', sys_dir])

    del register
    del monitor
    return presence_grp
