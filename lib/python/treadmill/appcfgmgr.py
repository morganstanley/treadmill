"""Listens to Treadmill cache events.

Applications that are scheduled to run on the server are mirrored in the
following directory structure::

    <treadmillroot>/
        cache/
            <instance>
        running/
            <instance> -> ../apps/<container_uniqueid>
        cleanup/
            <container_uniqueid> -> ../apps/<container_uniqueid>
        apps/
            <container_uniqueid>/...

Treadmill runs svscan process poiting to 'services' directory.

Upon change, appcfgmgr will do the following:

 - for each new manifest, create apps/<app> directory, app.json file and
   symlink from running/<app> to apps/<app_uniqueid>.
 - for each app that is not in the scheduled list, remove the symlink
 - trigger svscanctl -an, which will stop all apps that are no longer scheduled
   to run and will start all the new apps.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import glob
import logging
import os
import traceback

import six

from treadmill import appenv
from treadmill import appcfg
from treadmill import exc
from treadmill import eventmgr
from treadmill import fs
from treadmill import dirwatch
from treadmill import logcontext as lc
from treadmill import supervisor
from treadmill import utils

from treadmill.appcfg import configure as app_cfg
from treadmill.appcfg import abort as app_abort

_LOGGER = lc.Adapter(logging.getLogger(__name__))

_HEARTBEAT_SEC = 30
_WATCHDOG_TIMEOUT_SEC = _HEARTBEAT_SEC * 4


class AppCfgMgr:
    """Configure apps from the cache onto the node."""

    __slots__ = (
        'tm_env',
        '_is_active',
        '_runtime',
    )

    def __init__(self, root, runtime):
        _LOGGER.info('init appcfgmgr: %s, %s', root, runtime)
        self.tm_env = appenv.AppEnvironment(root=root)
        self._is_active = False
        self._runtime = runtime

    @property
    def name(self):
        """Name of the AppCfgMgr service.
        """
        return self.__class__.__name__

    def run(self):
        """Setup directories' watches and start the re-scan ticker.
        """
        # Start idle
        self._is_active = False

        # Setup the watchdog
        watchdog_lease = self.tm_env.watchdogs.create(
            name='svc-{svc_name}'.format(svc_name=self.name),
            timeout='{hb:d}s'.format(hb=_WATCHDOG_TIMEOUT_SEC),
            content='Service %r failed' % self.name
        )

        watch = dirwatch.DirWatcher(self.tm_env.cache_dir)
        watch.on_created = self._on_created
        watch.on_modified = self._on_modified
        watch.on_deleted = self._on_deleted

        # Start the timer
        watchdog_lease.heartbeat()

        while True:
            if watch.wait_for_events(timeout=_HEARTBEAT_SEC):
                watch.process_events(max_events=5)
            else:
                if self._is_active is True:
                    cached_files = glob.glob(
                        os.path.join(self.tm_env.cache_dir, '*')
                    )
                    running_links = glob.glob(
                        os.path.join(self.tm_env.running_dir, '*')
                    )
                    # Calculate the container names from every event file
                    cached_containers = {
                        appcfg.eventfile_unique_name(filename)
                        for filename in cached_files
                    }
                    # Calculate the instance names from every event running
                    # link
                    running_instances = {
                        os.path.basename(linkname)
                        for linkname in running_links
                    }
                    _LOGGER.debug('content of %r and %r: %r <-> %r',
                                  self.tm_env.cache_dir,
                                  self.tm_env.running_dir,
                                  cached_containers,
                                  running_instances)

                else:
                    _LOGGER.info('Still inactive during heartbeat event.')

            watchdog_lease.heartbeat()

        # Graceful shutdown.
        _LOGGER.info('service shutdown.')
        watchdog_lease.remove()

    def _on_modified(self, event_file):
        """Handle a modified cached manifest event.

        :param event_file:
            Full path to an event file
        :type event_file:
            ``str``
        """
        instance_name = os.path.basename(event_file)

        if instance_name == eventmgr.READY_FILE:
            self._first_sync()
            return

        elif instance_name[0] == '.':
            # Ignore all dot files
            return

        # NOTE(boysson): We ignore anything else for now.

    def _on_created(self, event_file):
        """Handle a new cached manifest event: configure an instance.

        :param event_file:
            Full path to an event file
        :type event_file:
            ``str``
        """
        instance_name = os.path.basename(event_file)

        if instance_name == eventmgr.READY_FILE:
            self._first_sync()
            return

        elif instance_name[0] == '.':
            # Ignore all dot files
            return

        elif self._is_active is False:
            # Ignore all created events while we are not running
            _LOGGER.debug('Inactive in created event handler.')
            return

        elif os.path.islink(os.path.join(self.tm_env.running_dir,
                                         instance_name)):
            _LOGGER.warning('Event on already configured %r',
                            instance_name)
            return

        elif self._configure(instance_name):
            self._refresh_supervisor()

    def _on_deleted(self, event_file):
        """Handle removal event of a cached manifest: terminate an instance.

        :param event_file:
            Full path to an event file
        :type event_file:
            ``str``
        """
        instance_name = os.path.basename(event_file)
        if instance_name == eventmgr.READY_FILE:
            _LOGGER.info('Cache folder not ready.'
                         ' Stopping processing of events.')
            self._is_active = False
            return

        elif instance_name[0] == '.':
            # Ignore all dot files
            return

        elif self._is_active is False:
            # Ignore all deleted events while we are not running
            _LOGGER.debug('Inactive in deleted event handler.')
            return

        else:
            self._terminate(instance_name)
            self._refresh_supervisor()

    def _first_sync(self):
        """Bring the appcfgmgr into active mode and do a first sync.
        """
        if self._is_active is not True:
            _LOGGER.info('Cache folder ready. Processing events.')
            self._is_active = True
            self._synchronize()

    def _synchronize(self):
        """Synchronize apps to running/cleanup.

        We need to re-validate three things on startup:

          - All configured apps should have an associated cache entry.
            Otherwise, create a link to cleanup.

          - All configured apps with a cache entry and with a cleanup file
            should be linked to cleanup. Otherwise, link to running.

          - Additional cache entries should be configured to run.

        On restart we need to validate another three things:

          - All configured apps that have a running link should be checked
            if in the cache. If not then terminate the app.

          - All configured apps that have a cleanup link should be left
            alone as this is handled.

          - Additional cache entries should be configured to run.

        On startup run.sh will clear running and cleanup which simplifies
        the logic for us as we can check running/cleanup first. Then check
        startup conditions and finally non-configured apps that are in cache.

        NOTE: a link cannot exist in running and cleanup at the same time.

        """
        # Disable R0912(too-many-branches)
        # pylint: disable=R0912
        configured = {
            os.path.basename(filename)
            for filename in glob.glob(os.path.join(self.tm_env.apps_dir, '*'))
        }
        cached = {
            os.path.basename(filename): appcfg.eventfile_unique_name(filename)
            for filename in glob.glob(os.path.join(self.tm_env.cache_dir, '*'))
        }

        for container in configured:
            appname = appcfg.app_name(container)
            if os.path.exists(os.path.join(self.tm_env.running_dir, appname)):
                # App already running.. check if in cache.
                # No need to check if needs cleanup as that is handled
                if appname not in cached or cached[appname] != container:
                    self._terminate(appname)
                else:
                    _LOGGER.info('Ignoring %s as it is running', appname)

                cached.pop(appname, None)

            elif os.path.exists(os.path.join(self.tm_env.cleanup_dir,
                                             appname)):
                # Already in the process of being cleaned up
                _LOGGER.info('Ignoring %s as it is in cleanup', appname)
                cached.pop(appname, None)

            else:
                needs_cleanup = True
                if appname in cached and cached[appname] == container:
                    data_dir = os.path.join(self.tm_env.apps_dir, container,
                                            'data')
                    for cleanup_file in ['exitinfo', 'aborted', 'oom']:
                        path = os.path.join(data_dir, cleanup_file)
                        if os.path.exists(path):
                            _LOGGER.debug('Found cleanup file %r', path)
                            break
                    else:
                        if self._configure(appname):
                            needs_cleanup = False
                            _LOGGER.debug('Added existing app %r', appname)

                    cached.pop(appname, None)

                if needs_cleanup:
                    fs.symlink_safe(
                        os.path.join(self.tm_env.cleanup_dir, appname),
                        os.path.join(self.tm_env.apps_dir, container)
                    )
                    _LOGGER.debug('Removed %r', appname)

        for appname in six.iterkeys(cached):
            if self._configure(appname):
                _LOGGER.debug('Added new app %r', appname)

        self._refresh_supervisor()

    def _configure(self, instance_name):
        """Configures and starts the instance based on instance cached event.

        - Runs app_configure --approot <rootdir> cache/<instance>

        :param ``str`` instance_name:
            Name of the instance to configure
        :returns ``bool``:
            True for successfully configured container.
        """
        event_file = os.path.join(
            self.tm_env.cache_dir,
            instance_name
        )

        with lc.LogContext(_LOGGER, instance_name):
            try:
                _LOGGER.info('Configuring')
                container_dir = app_cfg.configure(self.tm_env, event_file,
                                                  self._runtime)
                if container_dir is None:
                    # configure step failed, skip.
                    fs.rm_safe(event_file)
                    return False

                # symlink_safe(link, target)
                fs.symlink_safe(
                    os.path.join(self.tm_env.running_dir, instance_name),
                    container_dir
                )
                return True

            except exc.ContainerSetupError as err:  # pylint: disable=W0703
                _LOGGER.exception('Error configuring (%r)', instance_name)
                app_abort.report_aborted(self.tm_env, instance_name,
                                         why=err.reason,
                                         payload=traceback.format_exc())
                fs.rm_safe(event_file)
                return False
            except Exception as err:  # pylint: disable=W0703
                _LOGGER.exception('Error configuring (%r)', instance_name)
                app_abort.report_aborted(self.tm_env, instance_name,
                                         why=app_abort.AbortedReason.UNKNOWN,
                                         payload=traceback.format_exc())
                fs.rm_safe(event_file)
                return False

    def _terminate(self, instance_name):
        """Removes application from the supervised running list.

        Move the link from running directory to the cleanup directory.

        :param instance_name:
            Name of the instance to configure
        :type instance_name:
            ``str``
        """
        # In case the node is deleted from zookeeper (app is terminated),
        # the "services" directory still exists, and it is the job of
        # svscan to terminate the process.
        #
        # If services directory does not exist, app finished on it's own, and
        # the zk node was deleted by the cleanup script.
        #
        instance_run_link = os.path.join(
            self.tm_env.running_dir,
            instance_name
        )

        container_dir = self._resolve_running_link(instance_run_link)

        _LOGGER.info('terminating %sfinished %r (%r)',
                     ('not ' if os.path.exists(container_dir) else ''),
                     instance_name, container_dir)

        container_name = os.path.basename(container_dir)
        container_cleanup_link = os.path.join(
            self.tm_env.cleanup_dir,
            container_name
        )

        try:
            fs.replace(instance_run_link, container_cleanup_link)
            utils.touch(os.path.join(container_dir, 'data', 'terminated'))
        except OSError as err:
            # It is OK if the symlink is already removed (race with app own
            # cleanup).  Everything else is an error.
            if err.errno == errno.ENOENT:
                pass
            else:
                raise

    def _refresh_supervisor(self):
        """Notify the supervisor of new instances to run."""
        supervisor.control_svscan(self.tm_env.running_dir, (
            supervisor.SvscanControlAction.alarm,
            supervisor.SvscanControlAction.nuke
        ))

    @staticmethod
    def _resolve_running_link(running_link):
        """Safely resolve the running symbolic link.
        """
        try:
            container_dir = os.readlink(running_link)

        except OSError as err:
            # It is OK if the symlink is already removed.
            # Everything else is an error.
            if err.errno == errno.ENOENT:
                container_dir = ''
            else:
                raise

        return container_dir
