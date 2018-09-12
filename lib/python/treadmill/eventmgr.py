"""Listens to Treadmill server events.

There is single event manager process per server node.

Each server subscribes to the content of /servers/<servername> Zookeeper node.

The content contains the list of all apps currently scheduled to run on the
server.

Applications that are scheduled to run on the server are mirrored in the
'cache' directory.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import io
import logging
import os
import time

import kazoo
import kazoo.client

from treadmill import appenv
from treadmill import context
from treadmill import fs
from treadmill import sysinfo
from treadmill import utils
from treadmill import yamlwrapper as yaml
from treadmill import zknamespace as z
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)

_HEARTBEAT_SEC = 30
_WATCHDOG_TIMEOUT_SEC = _HEARTBEAT_SEC * 4

READY_FILE = '.ready'


class EventMgr:
    """Mirror Zookeeper scheduler event into node app cache events."""

    __slots__ = (
        'tm_env',
        '_hostname',
    )

    def __init__(self, root):
        _LOGGER.info('init eventmgr: %s', root)
        self.tm_env = appenv.AppEnvironment(root=root)

        self._hostname = sysinfo.hostname()

    @property
    def name(self):
        """Name of the EventMgr service.
        """
        return self.__class__.__name__

    def run(self, once=False):
        """Establish connection to Zookeeper and subscribes to node events."""
        # Setup the watchdog
        watchdog_lease = self.tm_env.watchdogs.create(
            name='svc-{svc_name}'.format(svc_name=self.name),
            timeout='{hb:d}s'.format(hb=_WATCHDOG_TIMEOUT_SEC),
            content='Service %r failed' % self.name
        )

        # Start the timer
        watchdog_lease.heartbeat()

        zkclient = context.GLOBAL.zk.conn
        zkclient.add_listener(zkutils.exit_on_lost)

        presence_ready = zkclient.handler.event_object()
        presence_ready.clear()

        placement_ready = zkclient.handler.event_object()
        placement_ready.clear()

        def _is_ready():
            return presence_ready.is_set() and placement_ready.is_set()

        @zkclient.DataWatch(z.path.server_presence(self._hostname))
        @utils.exit_on_unhandled
        def _server_presence_watch(data, _stat, event):
            """Watch server presence."""
            if data is None and event is None:
                _LOGGER.info('Presence node not found, waiting.')
                presence_ready.clear()
            elif event is not None and event.type == 'DELETED':
                _LOGGER.info('Presence node deleted.')
                presence_ready.clear()
            else:
                _LOGGER.info('Presence node found.')
                presence_ready.set()

            self._cache_notify(_is_ready())
            return True

        @utils.exit_on_unhandled
        def _app_watch(apps):
            """Watch application placement."""
            self._synchronize(
                zkclient, apps, check_existing=not placement_ready.is_set()
            )
            return True

        def _check_placement():
            if placement_ready.is_set():
                return

            if zkclient.exists(z.path.placement(self._hostname)):
                _LOGGER.info('Placement node found.')
                zkclient.ChildrenWatch(
                    z.path.placement(self._hostname), _app_watch
                )
                placement_ready.set()
                self._cache_notify(_is_ready())
            else:
                _LOGGER.info('Placement node not found, waiting.')

        while True:
            _check_placement()

            # Refresh watchdog
            watchdog_lease.heartbeat()
            time.sleep(_HEARTBEAT_SEC)

            self._cache_notify(_is_ready())

            if once:
                break

        # Graceful shutdown.
        _LOGGER.info('service shutdown.')
        watchdog_lease.remove()

    def _synchronize(self, zkclient, expected, check_existing=False):
        """Synchronize local app cache with the expected list.

        :param ``list`` expected:
            List of instances expected to be running on the server.
        :param ``bool`` check_existing:
            Whether to check if the already existing entries are up to date.
        """
        expected_set = set(expected)
        current_set = {
            os.path.basename(manifest)
            for manifest in glob.glob(os.path.join(self.tm_env.cache_dir, '*'))
        }
        extra = current_set - expected_set
        missing = expected_set - current_set
        existing = current_set & expected_set

        _LOGGER.info('expected : %s', ','.join(expected_set))
        _LOGGER.info('actual   : %s', ','.join(current_set))
        _LOGGER.info('extra    : %s', ','.join(extra))
        _LOGGER.info('missing  : %s', ','.join(missing))

        # If app is extra, remove the entry from the cache
        for app in extra:
            manifest = os.path.join(self.tm_env.cache_dir, app)
            os.unlink(manifest)

        # If app is missing, fetch its manifest in the cache
        for app in missing:
            self._cache(zkclient, app)

        if check_existing:
            _LOGGER.info('existing : %s', ','.join(existing))
            for app in existing:
                self._cache(zkclient, app, check_existing=True)

    def _cache(self, zkclient, app, check_existing=False):
        """Read the manifest and placement data from Zk and store it as YAML in
        <cache>/<app>.

        :param ``str`` app:
            Instance name.
        :param ``bool`` check_existing:
            Whether to check if the file already exists and is up to date.
        """
        placement_node = z.path.placement(self._hostname, app)
        try:
            placement_data, placement_metadata = zkutils.get_with_metadata(
                zkclient, placement_node
            )
            placement_time = placement_metadata.ctime / 1000.0
        except kazoo.exceptions.NoNodeError:
            _LOGGER.info('Placement %s/%s not found', self._hostname, app)
            return

        manifest_file = os.path.join(self.tm_env.cache_dir, app)
        if check_existing:
            try:
                manifest_time = os.stat(manifest_file).st_ctime
            except FileNotFoundError:
                manifest_time = None

            if manifest_time and manifest_time >= placement_time:
                _LOGGER.info('%s is up to date', manifest_file)
                return

        app_node = z.path.scheduled(app)
        try:
            manifest = zkutils.get(zkclient, app_node)
            # TODO: need a function to parse instance id from name.
            manifest['task'] = app[app.index('#') + 1:]

            if placement_data is not None:
                manifest.update(placement_data)

            fs.write_safe(
                manifest_file,
                lambda f: yaml.dump(manifest, stream=f),
                prefix='.%s-' % app,
                mode='w',
                permission=0o644
            )
            _LOGGER.info('Created cache manifest: %s', manifest_file)

        except kazoo.exceptions.NoNodeError:
            _LOGGER.info('App %s not found', app)

    def _cache_notify(self, is_ready):
        """Send a cache status notification event.

        Note: this needs to be an event, not a once time state change so
        that if appcfgmgr restarts after we enter the ready state, it will
        still get notified that we are ready.

        :params ``bool`` is_ready:
            True if the cache folder is ready.
        """
        _LOGGER.debug('cache notify (ready: %r)', is_ready)
        ready_file = os.path.join(self.tm_env.cache_dir, READY_FILE)
        if is_ready:
            # Mark the cache folder as ready.
            with io.open(ready_file, 'w'):
                pass
        else:
            # Mark the cache folder as outdated.
            fs.rm_safe(ready_file)
