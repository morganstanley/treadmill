"""List Treadmill endpoints matching a given pattern."""

import queue
import fnmatch
import logging

import kazoo

from treadmill import zknamespace as z

_LOGGER = logging.getLogger(__name__)


class Discovery(object):
    """Treadmill endpoint discovery."""

    def __init__(self, zkclient, pattern, endpoint):
        _LOGGER.debug('Treadmill discovery: %s:%s', pattern, endpoint)

        self.queue = queue.Queue()
        # Pattern is assumed to be in the form of <proid>.<pattern>
        self.prefix, self.pattern = pattern.split('.', 1)
        if self.pattern.find('#') == -1:
            self.pattern = self.pattern + '#*'
        self.endpoint = endpoint

        self.state = set()
        self.zkclient = zkclient

    def iteritems(self, block=True, timeout=None):
        """List matching endpoints. """
        while True:
            try:
                endpoint, hostport = self.queue.get(block, timeout)
                if (endpoint, hostport) == (None, None):
                    break
                yield (endpoint, hostport)
            except queue.Empty:
                break

    def apps_watcher(self, event):
        """Watch for created/deleted apps that match monitored pattern."""
        _LOGGER.debug('apps_watcher: %s', event)
        self.sync()

    def sync(self, watch=True):
        """Find matching endpoints and put them on the queue for processing.

        If watch is True, establish a watch on /apps for new changes,
        otherwise put termination signal into the queue.
        """
        watch_cb = None
        if watch:
            watch_cb = self.apps_watcher

        match = self.get_endpoints_zk(watch_cb=watch_cb)

        created = match - set(self.state)
        deleted = set(self.state) - match

        for endpoint in created:
            _LOGGER.debug('added endpoint: %s', endpoint)
            hostport = self.resolve_endpoint(endpoint)
            self.queue.put(('.'.join([self.prefix, endpoint]), hostport))

        for endpoint in deleted:
            _LOGGER.debug('deleted endpoint: %s', endpoint)
            self.queue.put(('.'.join([self.prefix, endpoint]), None))

        self.state = match

    def snapshot(self):
        """Returns the current state of the matching endpoints."""
        return ['.'.join([self.prefix, endpoint]) for endpoint in self.state]

    def exit_loop(self):
        """Put termination event on the queue."""
        self.queue.put((None, None))

    def get_endpoints(self):
        """Returns the current list of endpoints in host:port format"""
        endpoints = self.get_endpoints_zk()
        hostports = [self.resolve_endpoint(endpoint)
                     for endpoint in endpoints]
        return hostports

    def get_endpoints_zk(self, watch_cb=None):
        """Returns the current list of endpoints."""
        endpoints_path = z.join_zookeeper_path(z.ENDPOINTS, self.prefix)
        full_pattern = ':'.join([self.pattern, '*', self.endpoint])
        try:
            endpoints = self.zkclient.get_children(
                endpoints_path, watch=watch_cb
            )

            match = set([endpoint for endpoint in endpoints
                         if fnmatch.fnmatch(endpoint, full_pattern)])
        except kazoo.exceptions.NoNodeError:
            self.zkclient.exists(endpoints_path, watch=watch_cb)
            match = set()

        return match

    def resolve_endpoint(self, endpoint):
        """Resolves a endpoint to a hostport"""
        fullpath = z.join_zookeeper_path(z.ENDPOINTS, self.prefix, endpoint)
        try:
            hostport, _metadata = self.zkclient.get(fullpath)
        except kazoo.exceptions.NoNodeError:
            hostport = None

        return hostport


def iterator(zkclient, pattern, endpoint, watch):
    """Returns app discovery iterator based on native zk discovery."""
    app_discovery = Discovery(zkclient, pattern, endpoint)
    app_discovery.sync()
    if not watch:
        app_discovery.exit_loop()

    for (app, hostport) in app_discovery.items():
        yield app, hostport
