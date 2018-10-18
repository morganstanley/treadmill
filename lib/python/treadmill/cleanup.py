"""Listens to Treadmill cleanup events.

When a treadmill app needs to be cleaned up then there will exist a symlink
to the app in the cleanup directory. A cleanup app will be created to do
the cleanup work necessary:

    <treadmillroot>/
        cleanup/
            <instance>
        cleaning/
            <instance> -> ../cleanup_apps/<instance>
        cleanup_apps/
            <instance>

Treadmill runs svscan process pointing to 'cleaning' scan directory.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import logging
import os
import shutil
import time

from treadmill import dirwatch
from treadmill import fs
from treadmill import logcontext as lc
from treadmill import runtime as app_runtime
from treadmill import subproc
from treadmill import supervisor


_LOGGER = logging.getLogger(__name__)

# FIXME: This extremely high timeout value comes from the fact that we
#        have a very high watchdog value in runtime.
_WATCHDOG_HEARTBEAT_SEC = 5 * 60

# Maximum number of cleanup request to process per cycle. Be careful of
# watchdog timeouts when increasing this value.
_MAX_REQUEST_PER_CYCLE = 1

_SERVICE_NAME = 'Cleanup'


class Cleanup:
    """Orchestrate the cleanup of apps which are scheduled to be stopped and/or
    removed.
    """

    __slots__ = (
        'tm_env',
    )

    def __init__(self, tm_env):
        self.tm_env = tm_env

    def _refresh_supervisor(self):
        """Notify the supervisor of new cleanup instances.
        """
        _LOGGER.info('Refreshing svscan')

        supervisor.control_svscan(self.tm_env.cleaning_dir, (
            supervisor.SvscanControlAction.alarm,
            supervisor.SvscanControlAction.nuke
        ))

    def _add_cleanup_app(self, path):
        """Configure a new cleanup app.
        """
        name = os.path.basename(path)

        if name.startswith('.'):
            _LOGGER.warning('Ignore %s', name)
            return

        cleaning_link = os.path.join(self.tm_env.cleaning_dir, name)
        if os.path.islink(cleaning_link):
            _LOGGER.warning('Cleaning app already configured %s', name)
            return

        cleanup_link = os.path.join(self.tm_env.cleanup_dir, name)
        if not os.path.islink(cleanup_link):
            _LOGGER.info('Ignore - not a link: %s', cleanup_link)
            return

        _LOGGER.info('Configure cleaning app: %s', name)

        bin_name = 'scripts' if os.name == 'nt' else 'bin'
        command = (
            '{treadmill}/{bin}/treadmill sproc cleanup instance'
            ' --approot {tm_root}'
            ' {instance}'
        ).format(
            treadmill=subproc.resolve('treadmill'),
            bin=bin_name,
            tm_root=self.tm_env.root,
            instance=name
        )

        if os.name == 'posix':
            command = 'exec ' + command

        supervisor.create_service(
            self.tm_env.cleanup_apps_dir,
            name=name,
            app_run_script=command,
            userid='root',
            monitor_policy={
                'limit': 5,
                'interval': 60,
                'tombstone': {
                    'path': self.tm_env.cleanup_tombstone_dir,
                    'id': name,
                },
                'skip_path': os.path.join(self.tm_env.cleanup_dir, name)
            },
            log_run_script=None,
        )

        fs.symlink_safe(
            cleaning_link,
            os.path.join(self.tm_env.cleanup_apps_dir, name)
        )

        _LOGGER.debug('Cleanup app %s ready', name)

        self._refresh_supervisor()

    def _remove_cleanup_app(self, path):
        """Stop and remove a cleanup app.
        """
        name = os.path.basename(path)

        if name.startswith('.'):
            _LOGGER.warning('Ignore %s', name)
            return

        cleaning_link = os.path.join(self.tm_env.cleaning_dir, name)
        app_path = os.path.join(self.tm_env.cleanup_apps_dir, name)

        _LOGGER.info('Removing cleanup app %s -> %s', cleaning_link, app_path)

        if os.path.exists(cleaning_link):
            _LOGGER.debug('Removing cleanup link %s', cleaning_link)
            fs.rm_safe(cleaning_link)
            self._refresh_supervisor()
            _LOGGER.debug('Waiting on %s not being supervised', app_path)
            supervisor.ensure_not_supervised(app_path)
        else:
            _LOGGER.debug('Cleanup link %s does not exist', cleaning_link)

        _LOGGER.debug('Removing app directory %s', app_path)
        fs.rmtree_safe(app_path)

    def invoke(self, runtime, instance, runtime_param=None):
        """Actually do the cleanup of the instance.
        """
        cleanup_link = os.path.join(self.tm_env.cleanup_dir, instance)
        container_dir = os.readlink(cleanup_link)
        _LOGGER.info('Cleanup: %s => %s', instance, container_dir)
        if os.path.exists(container_dir):
            with lc.LogContext(_LOGGER, os.path.basename(container_dir),
                               lc.ContainerAdapter) as log:
                try:
                    app_runtime.get_runtime(
                        runtime, self.tm_env, container_dir, runtime_param
                    ).finish()
                except supervisor.InvalidServiceDirError:
                    log.info('Container dir is invalid, removing: %s',
                             container_dir)
                    shutil.rmtree(container_dir)
                except Exception:  # pylint: disable=W0703
                    if not os.path.exists(container_dir):
                        log.info('Container dir does not exist: %s',
                                 container_dir)
                    else:
                        log.exception('Fatal error running finish %r.',
                                      container_dir)
                        raise

        else:
            _LOGGER.info('Container dir does not exist: %r', container_dir)

        fs.rm_safe(cleanup_link)

    def _sync(self):
        """Synchronize cleanup to cleaning.
        """
        cleanup_list = [
            os.path.basename(filename)
            for filename in glob.glob(os.path.join(self.tm_env.cleanup_dir,
                                                   '*'))
        ]
        cleanup_apps = {
            os.path.basename(filename)
            for filename in glob.glob(
                os.path.join(self.tm_env.cleanup_apps_dir, '*')
            )
        }

        for instance in cleanup_list:
            self._add_cleanup_app(instance)
            cleanup_apps.discard(instance)

        for instance in cleanup_apps:
            self._remove_cleanup_app(instance)

    def run(self):
        """Setup directories' watches and start the re-scan ticker.
        """
        # Setup the watchdog
        watchdog_lease = self.tm_env.watchdogs.create(
            name='svc-{svc_name}'.format(svc_name=_SERVICE_NAME),
            timeout='{hb:d}s'.format(hb=_WATCHDOG_HEARTBEAT_SEC),
            content='Service {svc_name!r} failed'.format(
                svc_name=_SERVICE_NAME),
        )

        # Wait on svscan starting up first to avoid race conditions with
        # refreshing it later.
        while True:
            try:
                self._refresh_supervisor()
                _LOGGER.info('svscan is running.')
                break
            except subproc.CalledProcessError:
                _LOGGER.info('Waiting on svscan running.')
                time.sleep(0.2)

        watcher = dirwatch.DirWatcher(self.tm_env.cleanup_dir)
        watcher.on_created = self._add_cleanup_app
        watcher.on_deleted = self._remove_cleanup_app

        self._sync()

        loop_timeout = _WATCHDOG_HEARTBEAT_SEC // 2
        while True:
            if watcher.wait_for_events(timeout=loop_timeout):
                watcher.process_events(max_events=_MAX_REQUEST_PER_CYCLE)

            # Heartbeat
            watchdog_lease.heartbeat()

        _LOGGER.info('Cleanup service shutdown.')
        watchdog_lease.remove()
