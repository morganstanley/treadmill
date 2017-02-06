"""Listens to Treadmill server events.

There is single event manager process per server node.

Each server subscribes to the content of /servers/<servername> Zookeeper node.

The content contains the list of all apps currently scheduled to run on the
server.

Applications that are scheduled to run on the server are mirrored in the
'cache' directory.
"""


import os
import time

import glob
import logging
import tempfile

import kazoo
import kazoo.client

import yaml

from . import appmgr
from . import context
from . import exc
from . import fs
from . import sysinfo
from . import zkutils
from . import zknamespace as z


_LOGGER = logging.getLogger(__name__)

_HEARTBEAT_SEC = 30
_WATCHDOG_TIMEOUT_SEC = _HEARTBEAT_SEC * 2
_SEEN_FILE = '.seen'


class EventMgr(object):
    """Mirror Zookeeper scheduler event into node app cache events."""

    __slots__ = (
        'tm_env',
        '_hostname',
    )

    def __init__(self, root):
        _LOGGER.info('init eventmgr: %s', root)
        self.tm_env = appmgr.AppEnvironment(root=root)

        self._hostname = sysinfo.hostname()

    @property
    def name(self):
        """Name of the EventMgr service.
        """
        return self.__class__.__name__

    def run(self):
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

        seen = zkclient.handler.event_object()
        # Start not ready
        seen.clear()

        # Wait for presence node to appear. Once up, syncronize the placement.
        @zkclient.DataWatch(z.path.server_presence(self._hostname))
        @exc.exit_on_unhandled
        def _server_presence_update(data, _stat, event):
            """Watch server presence."""
            if data is None and event is None:
                # The node is not there yet, wait.
                _LOGGER.info('Server node missing.')
                seen.clear()
                self._cache_notify(False)
            elif event is not None and event.type == 'DELETED':
                _LOGGER.info('Presence node deleted.')
                seen.clear()
                self._cache_notify(False)
            else:
                _LOGGER.info('Presence is up.')
                seen.set()
                apps = zkclient.get_children(z.path.placement(self._hostname))
                self._synchronize(zkclient, apps)
            return True

        @zkclient.ChildrenWatch(z.path.placement(self._hostname))
        @exc.exit_on_unhandled
        def _app_watch(apps):
            """Watch application placement."""
            if seen.is_set():
                self._synchronize(zkclient, apps)
                self._cache_notify(True)
            return True

        while True:
            # Refresh watchdog
            watchdog_lease.heartbeat()
            time.sleep(_HEARTBEAT_SEC)
            self._cache_notify(seen.is_set())

        # Graceful shutdown.
        _LOGGER.info('service shutdown.')
        watchdog_lease.remove()

    def _synchronize(self, zkclient, expected):
        """synchronize local app cache with the expected list.

        :param expected:
            List of instances expected to be running on the server.
        :type expected:
            ``list``
        """
        expected_set = set(expected)
        current_set = {
            os.path.basename(manifest)
            for manifest in glob.glob(os.path.join(self.tm_env.cache_dir, '*'))
        }
        extra = current_set - expected_set
        missing = expected_set - current_set

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

    def _cache(self, zkclient, app):
        """Reads the manifest from Zk and stores it as YAML in <cache>/<app>.
        """
        appnode = z.path.scheduled(app)
        placement_node = z.path.placement(self._hostname, app)
        manifest_file = None
        try:
            manifest = zkutils.get(zkclient, appnode)
            # TODO: need a function to parse instance id from name.
            manifest['task'] = app[app.index('#') + 1:]

            placement_info = zkutils.get(zkclient, placement_node)
            if placement_info is not None:
                manifest.update(placement_info)

            manifest_file = os.path.join(self.tm_env.cache_dir, app)
            with tempfile.NamedTemporaryFile(dir=self.tm_env.cache_dir,
                                             prefix='.%s-' % app,
                                             delete=False,
                                             mode='w') as temp_manifest:
                yaml.dump(manifest, stream=temp_manifest)
            os.rename(temp_manifest.name, manifest_file)
            _LOGGER.info('Created cache manifest: %s', manifest_file)

        except kazoo.exceptions.NoNodeError:
            _LOGGER.warning('App %r not found', app)

    def _cache_notify(self, is_seen):
        """Sent a cache status notification event.

        Note: this needs to be an event, not a once time state change so
        that if appcfgmgr restarts after we enter the ready state, it will
        still get notified that we are ready.

        :params ``bool`` is_seen:
            True if the server is seen by the scheduler.
        """
        _LOGGER.debug("cache notify (seen: %r)", is_seen)
        if is_seen:
            # Mark the cache folder as ready.
            with open(os.path.join(self.tm_env.cache_dir, _SEEN_FILE), 'w+'):
                pass
        else:
            # Mark the cache folder as outdated.
            fs.rm_safe(os.path.join(self.tm_env.cache_dir, _SEEN_FILE))
