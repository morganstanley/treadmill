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

 - for each new manifest, create apps/<app> directory, app.yml file and
   symlink from running/<app> to apps/<app_uniqueid>.
 - for each app that is not in the scheduled list, remove the symlink
 - trigger svscanctl -an, which will stop all apps that are no longer scheduled
   to run and will start all the new apps.
"""


import errno
import glob
import logging
import os
import time

from . import appmgr
from . import fs
from . import idirwatch
from . import logcontext as lc
from . import subproc
from .appmgr import configure as app_cfg
from .appmgr import abort as app_abort

if os.name == 'nt':
    from .syscall import winsymlink  # noqa: F401

_LOGGER = lc.Adapter(logging.getLogger(__name__))


_HEARTBEAT_SEC = 30
_WATCHDOG_TIMEOUT_SEC = _HEARTBEAT_SEC * 4


class AppCfgMgr(object):
    """Configure apps from the cache onto the node."""

    __slots__ = (
        'tm_env',
        '_is_active',
    )

    def __init__(self, root):
        _LOGGER.info('init appcfgmgr: %s', root)
        self.tm_env = appmgr.AppEnvironment(root=root)
        self._is_active = False

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

        watch = idirwatch.DirWatcher(self.tm_env.cache_dir)
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
                        appmgr.eventfile_unique_name(filename)
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

        if instance_name == '.seen':
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

        if instance_name == '.seen':
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

        else:
            self._configure(instance_name)
            self._refresh_supervisor(instance_names=[instance_name])

    def _on_deleted(self, event_file):
        """Handle removal event of a cached manifest: terminate an instance.

        :param event_file:
            Full path to an event file
        :type event_file:
            ``str``
        """
        instance_name = os.path.basename(event_file)
        if instance_name == '.seen':
            _LOGGER.info('Cache folder not ready.'
                         ' Stoping processing of events.')
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
        """Synchronize cache/ instances with running/ instances.

        We need to revalidate three things:

          - All running instances must have an equivalent entry in cache or be
            terminated.

          - All event files in the cache that do not have running link must be
            started.

          - The cached entry and the running link must be for the same
            container (equal unique name). Otherwise, terminate it.

        """
        cached_files = glob.glob(os.path.join(self.tm_env.cache_dir, '*'))
        running_links = glob.glob(os.path.join(self.tm_env.running_dir, '*'))

        # Calculate the instance names from every event file
        cached_instances = {
            os.path.basename(filename)
            for filename in cached_files
        }
        # Calculate the container names from every event file
        cached_containers = {
            appmgr.eventfile_unique_name(filename)
            for filename in cached_files
        }
        # Calculate the instance names from every event running link
        running_instances = {
            os.path.basename(linkname)
            for linkname in running_links
            if os.path.islink(linkname)
        }
        removed_instances = set()
        added_instances = set()

        _LOGGER.info('running %r', running_instances)
        # If instance is extra, remove the symlink and force svscan to
        # re-evaluate
        for instance_link in running_links:
            # Skip any files and directories (created by svscan). The footprint
            # that defines the app is the symlink:
            # - running/<instance_name> -> apps/<container_name>
            #
            # Iterate over all symlinks, skipping other files and directories.
            if not os.path.islink(instance_link):
                continue

            instance_name = os.path.basename(instance_link)
            _LOGGER.info('checking %r', instance_link)
            if not os.path.exists(instance_link):
                # Broken symlink, something went wrong.
                _LOGGER.warning('broken link %r', instance_link)
                os.unlink(instance_link)
                removed_instances.add(instance_name)
                continue

            elif instance_name not in cached_instances:
                self._terminate(instance_name)
                removed_instances.add(instance_name)

            else:
                # Now check that the link match the intended container
                container_dir = self._resolve_running_link(instance_link)
                container_name = os.path.basename(container_dir)
                if container_name not in cached_containers:
                    self._terminate(instance_name)
                    removed_instances.add(instance_name)

        # For all new apps, read the manifest and configure the app. When all
        # apps are configured, force rescan again.
        for instance_name in cached_instances:
            instance_link = os.path.join(
                self.tm_env.running_dir,
                instance_name
            )
            self._configure(instance_name)
            added_instances.add(instance_name)

        _LOGGER.debug('End resuld: %r / %r - %r + %r',
                      cached_containers,
                      running_instances,
                      removed_instances,
                      added_instances)

        running_instances -= removed_instances
        running_instances |= added_instances
        _LOGGER.info('running post cleanup: %r', running_instances)
        self._refresh_supervisor(instance_names=running_instances)

    def _configure(self, instance_name):
        """Configures and starts the instance based on instance cached event.

        - Runs app_configure --approot <rootdir> cache/<instance>

        :param instance_name:
            Name of the instance to configure
        :type instance_name:
            ``str``
        """
        event_file = os.path.join(
            self.tm_env.cache_dir,
            instance_name
        )

        with lc.LogContext(_LOGGER, instance_name):
            try:
                _LOGGER.info('Configuring')
                container_dir = app_cfg.configure(self.tm_env, event_file)
                app_cfg.schedule(
                    container_dir,
                    os.path.join(self.tm_env.running_dir, instance_name)
                )

            except Exception as err:  # pylint: disable=W0703
                _LOGGER.exception('Error configuring (%r)', event_file)
                app_abort.abort(self.tm_env, event_file, err)
                fs.rm_safe(event_file)

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
            os.rename(instance_run_link, container_cleanup_link)

        except OSError as err:
            # It is OK if the symlink is already removed (race with app own
            # cleanup).  Everything else is an error.
            if err.errno == errno.ENOENT:
                pass
            else:
                raise

    def _refresh_supervisor(self, instance_names=()):
        """Notify the supervisor of new instances to run."""
        subproc.check_call(
            [
                's6-svscanctl',
                '-an',
                self.tm_env.running_dir
            ]
        )
        for instance_name in instance_names:
            with lc.LogContext(_LOGGER, instance_name):
                _LOGGER.info('Starting')
                instance_run_link = os.path.join(
                    self.tm_env.running_dir,
                    instance_name
                )
                # Wait for the supervisor to pick up the new instance.
                for _ in range(10):
                    res = subproc.call(
                        [
                            's6-svok',
                            instance_run_link,
                        ]
                    )
                    if res == 0:
                        break
                    else:
                        _LOGGER.warning('Supervisor has not picked it up yet')
                        time.sleep(0.5)
                # Bring the instance up.
                subproc.check_call(
                    [
                        's6-svc',
                        '-uO',
                        instance_run_link,
                    ]
                )

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
