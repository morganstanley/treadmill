"""Linux runtime interface.
"""

import time
import logging
import os

from treadmill import appcfg
from treadmill import context
from treadmill import exc
from treadmill import presence
from treadmill import subproc
from treadmill import supervisor
from treadmill import tickets

from treadmill.appcfg import abort as app_abort
from treadmill.runtime import runtime_base

from . import _run as app_run
from . import _finish as app_finish


_LOGGER = logging.getLogger(__name__)


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
    tkts_spool_dir = os.path.join(
        container_dir, 'root', 'var', 'spool', 'tickets')

    reply = tickets.request_tickets(context.GLOBAL.zk.conn, appname)
    if reply:
        tickets.store_tickets(reply, tkts_spool_dir)

    # Check that all requested tickets are valid.
    for princ in app.get('tickets', []):
        krbcc_file = os.path.join(tkts_spool_dir, princ)
        if not tickets.krbcc_ok(krbcc_file):
            _LOGGER.error('Missing or expired tickets: %s, %s',
                          princ, krbcc_file)
            raise exc.ContainerSetupError('tickets.%s' % princ)
        else:
            _LOGGER.info('Ticket ok: %s, %s', princ, krbcc_file)


class LinuxRuntime(runtime_base.RuntimeBase):
    """Linux Treadmill runtime."""

    def __init__(self, tm_env, container_dir):
        super(LinuxRuntime, self).__init__(tm_env, container_dir)

    def _can_run(self, manifest):
        try:
            # TODO: Add support for TAR (and maybe DOCKER)
            return appcfg.AppType(manifest['type']) is appcfg.AppType.NATIVE
        except ValueError:
            return False

    def _run(self, manifest, watchdog, terminated):
        # Apply memory limits first thing after start, so that app_run
        # does not consume memory from treadmill/core.
        app_run.apply_cgroup_limits(self.tm_env, self.container_dir, manifest)

        if not terminated:
            app_run.run(self.tm_env, self.container_dir, manifest, watchdog,
                        terminated)

    def _finish(self):
        app_finish.finish(self.tm_env, context.GLOBAL.zk.conn,
                          self.container_dir)

    def _register(self, manifest, refresh_interval=None):
        app_presence = presence.EndpointPresence(
            context.GLOBAL.zk.conn,
            manifest
        )

        try:
            app_presence.register()
            _get_tickets(manifest['name'], manifest, self.container_dir)
            _start_service_sup(self.container_dir)
        except exc.ContainerSetupError as err:
            app_abort.abort(
                self.tm_env,
                manifest['name'],
                reason=str(err)
            )

        # If tickets are not ok, app will be aborted. Waiting for tickets
        # in the loop is harmless way to wait for that.
        #
        # If tickets acquired successfully, services will start, and
        # tickets will be refreshed after each interval.
        tkts_spool_dir = os.path.join(
            self.container_dir, 'root', 'var', 'spool', 'tickets')

        while True:
            time.sleep(refresh_interval)
            reply = tickets.request_tickets(context.GLOBAL.zk.conn,
                                            manifest['name'])
            if reply:
                tickets.store_tickets(reply, tkts_spool_dir)
            else:
                _LOGGER.error('Error requesting tickets.')

    def _monitor(self, manifest):
        svc_presence = presence.ServicePresence(
            manifest,
            self.container_dir,
            self.tm_env.app_events_dir
        )

        sys_dir = os.path.join(self.container_dir, 'sys')
        svc_sup_dir = os.path.join(sys_dir, 'start_container')

        failed_svc = None
        killed = False

        # Check that start_container was not terminated. This fixed race
        # condition if the presence exits and while restarted,
        # start_container is terminated.
        svc_sup_ran_once = os.path.exists(os.path.join(svc_sup_dir,
                                                       'self.pid'))
        _LOGGER.info('services supervisor ran once: %s', svc_sup_ran_once)
        svc_sup_down = presence.is_down(svc_sup_dir)
        _LOGGER.info('services supervisor down: %s', svc_sup_down)
        if svc_sup_down and svc_sup_ran_once:
            _LOGGER.info('services supervisor was terminated, exiting.')
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
                    _LOGGER.info('Container services supervisor is down.')
                    failed_svc = None
                    killed = True
                    break

        svc_presence.exit_app(failed_svc, killed=killed)

        _LOGGER.info('Shutting down sys supervisor.')
        subproc.call(['s6_svscanctl', '-pi', sys_dir])
