"""Runs Treadmill application presence daemon."""


import time
import logging
import os

import click
import yaml

from treadmill import appmgr
from treadmill import exc
from treadmill import presence
from treadmill import context
from treadmill import logcontext as lc
from treadmill import subproc
from treadmill import supervisor
from treadmill import tickets
from treadmill import zkutils
from treadmill.appmgr import abort as app_abort


_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))

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


def _get_tickets(appname, app, container_dir):
    """Get tickets."""
    with lc.LogContext(_LOGGER, appname, lc.ContainerAdapter) as log:
        tkts_spool_dir = os.path.join(
            container_dir, 'root', 'var', 'spool', 'tickets')

        reply = tickets.request_tickets(context.GLOBAL.zk.conn, appname)
        if reply:
            tickets.store_tickets(reply, tkts_spool_dir)

        # Check that all requested tickets are valid.
        for princ in app.get('tickets', []):
            krbcc_file = os.path.join(tkts_spool_dir, princ)
            if not tickets.krbcc_ok(krbcc_file):
                log.error('Missing or expired tickets: %s, %s',
                          princ, krbcc_file)
                raise exc.ContainerSetupError('tickets.%s' % princ)
            else:
                _LOGGER.info('Ticket ok: %s, %s', princ, krbcc_file)


def init():
    """App main."""

    @click.group(name='presence')
    def presence_grp():
        """Register container/app presence."""
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)

    @presence_grp.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--refresh-interval', type=int,
                  default=_TICKETS_REFRESH_INTERVAL)
    @click.argument('manifest', type=click.File('rb'))
    @click.argument('container-dir', type=click.Path(exists=True))
    @click.argument('appevents-dir', type=click.Path(exists=True))
    def register(approot, refresh_interval, manifest, container_dir,
                 appevents_dir):
        """Register container presence."""
        del appevents_dir
        tm_env = appmgr.AppEnvironment(approot)

        app = yaml.load(manifest.read())
        appname = app['name']

        with lc.LogContext(_LOGGER, appname, lc.ContainerAdapter) as log:
            app_presence = presence.EndpointPresence(
                context.GLOBAL.zk.conn,
                app
            )

            try:
                app_presence.register()
                _get_tickets(appname, app, container_dir)
                _start_service_sup(container_dir)
            except exc.ContainerSetupError as err:
                app_abort.abort(
                    tm_env,
                    appname,
                    reason=str(err)
                )

            # If tickets are not ok, app will be aborted. Waiting for tickets
            # in the loop is harmless way to wait for that.
            #
            # If tickets acquired successfully, services will start, and
            # tickets will be refreshed after each interval.
            tkts_spool_dir = os.path.join(
                container_dir, 'root', 'var', 'spool', 'tickets')

            while True:
                time.sleep(refresh_interval)
                reply = tickets.request_tickets(context.GLOBAL.zk.conn,
                                                appname)
                if reply:
                    tickets.store_tickets(reply, tkts_spool_dir)
                else:
                    log.error('Error requesting tickets.')

    @presence_grp.command()
    @click.argument('manifest', type=click.File('rb'))
    @click.argument('container-dir', type=click.Path(exists=True))
    @click.argument('appevents-dir', type=click.Path(exists=True))
    def monitor(manifest, container_dir, appevents_dir):
        """Monitor container services."""
        app = yaml.load(manifest.read())
        with lc.LogContext(_LOGGER, app['name'], lc.ContainerAdapter) as log:
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
            # condition if the presence exits and while restarted,
            # start_container is terminated.
            svc_sup_ran_once = os.path.exists(os.path.join(svc_sup_dir,
                                                           'self.pid'))
            log.logger.info(
                'services supervisor ran once: %s', svc_sup_ran_once
            )
            svc_sup_down = presence.is_down(svc_sup_dir)
            log.logger.info('services supervisor down: %s', svc_sup_down)
            if svc_sup_down and svc_sup_ran_once:
                log.logger.info('services supervisor was terminated, exiting.')
            else:
                svc_presence.ensure_supervisors_running()

                # Try to start the service, taking into account number of
                # restarts.
                # If the number of restarts is more than specified, delete app
                # from the model, which will trigger container shutdown.
                #
                # In case of container shutdown (application evicted from the
                # server), exit_app will not be called.
                while True:
                    success, failed_svc = svc_presence.start_all()
                    if not success:
                        break

                    svc_presence.wait_for_exit(svc_sup_dir)
                    if presence.is_down(svc_sup_dir):
                        log.logger.info(
                            'Container services supervisor is down.'
                        )
                        failed_svc = None
                        killed = True
                        break

            svc_presence.exit_app(failed_svc, killed=killed)

            log.logger.info('Shutting down sys supervisor.')
            subproc.call(['s6-svscanctl', '-pi', sys_dir])

    del register
    del monitor
    return presence_grp
