"""List Treadmill endpoints matching a given pattern.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import fnmatch
import logging

import kazoo.exceptions

from six.moves import queue

from treadmill import zknamespace as z

_LOGGER = logging.getLogger(__name__)


def _join_prefix(prefix, arg):
    """Return arg with the provided prefix joined."""
    return '.'.join([prefix, arg])


def _split_prefix(arg):
    """Return a list containing: [prefix, arg_wo_prefix]."""
    return arg.split('.', 1)


class Discovery:
    """Treadmill endpoint discovery."""

    def __init__(self, zkclient, pattern, endpoint):
        _LOGGER.debug('Treadmill discovery: %s:%s', pattern, endpoint)

        self.queue = queue.Queue()

        # Pattern is assumed to be in the form of <proid>.<pattern>
        patterns = [pattern] if not isinstance(pattern, list) else pattern
        self.patterns = [
            pattern if '#' in pattern else pattern + '#*'
            for pattern in patterns
        ]

        self.endpoint = endpoint

        self.state = set()
        self.zkclient = zkclient

    def iteritems(self, block=True, timeout=None):
        """List matching endpoints."""
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

        # let's read self.state only once as this func can be executed
        # simultaneously (it's a Zk callback func)
        state = set(self.state)
        created = match - state
        deleted = state - match

        for endpoint in created:
            _LOGGER.debug('added endpoint: %s', endpoint)
            hostport = self.resolve_endpoint(endpoint)
            self.queue.put((endpoint, hostport))

        for endpoint in deleted:
            _LOGGER.debug('deleted endpoint: %s', endpoint)
            self.queue.put((endpoint, None))

        self.state = match

    def snapshot(self):
        """Returns the current state of the matching endpoints."""
        return list(self.state)

    def exit_loop(self):
        """Put termination event on the queue."""
        self.queue.put((None, None))

    def get_endpoints(self):
        """Returns the current list of endpoints in host:port format"""
        endpoints = self.get_endpoints_zk()
        hostports = [self.resolve_endpoint(endpoint) for endpoint in endpoints]
        return hostports

    def get_endpoints_zk(self, watch_cb=None):
        """
        Returns the current list of endpoints in the form of
        <proid>.endpoint_filename.
        """
        match = set()
        for prefix in self._prefixes():
            endpoints_path = z.join_zookeeper_path(z.ENDPOINTS, prefix)
            try:
                endpoints = [
                    _join_prefix(prefix, endpoint) for endpoint in
                    self.zkclient.get_children(endpoints_path, watch=watch_cb)
                ]
            except kazoo.exceptions.NoNodeError:
                if watch_cb:
                    self.zkclient.exists(endpoints_path, watch=watch_cb)
                endpoints = []

            match = match | self._matching_endpoints(endpoints)

        _LOGGER.debug('pattern matching endpoints: %s', match)
        return match

    def _prefixes(self):
        """Return the unique application proids based on self.patterns."""
        # Pattern is assumed to be in the form of <proid>.<pattern>
        return {_split_prefix(pattern)[0] for pattern in self.patterns}

    def _matching_endpoints(self, endpoints):
        """Returns the list of endpoints matching one of the patterns."""
        # Pattern is assumed to be in the form of <proid>.<pattern>
        # Endpoint is assumed to be in the form of <proid>.endpoint_filename
        match = set()
        for pattern in self.patterns:
            full_pattern = ':'.join([pattern, '*', self.endpoint])
            match = match | {endpoint for endpoint in endpoints
                             if fnmatch.fnmatch(endpoint, full_pattern)}

        return match

    def resolve_endpoint(self, endpoint):
        """Resolves a endpoint to a hostport"""
        # Endpoint is assumed to be in the form of <proid>.endpoint_filename
        prefix, endpoint_fname = _split_prefix(endpoint)
        fullpath = z.join_zookeeper_path(z.ENDPOINTS, prefix, endpoint_fname)
        try:
            hostport, _metadata = self.zkclient.get(fullpath)
            hostport = hostport.decode()
        except kazoo.exceptions.NoNodeError:
            hostport = None

        return hostport


def iterator(zkclient, pattern, endpoint, watch):
    """Returns app discovery iterator based on native zk discovery.
    """
    app_discovery = Discovery(zkclient, pattern, endpoint)
    app_discovery.sync(watch)
    if not watch:
        app_discovery.exit_loop()

    for (app, hostport) in app_discovery.iteritems():
        yield app, hostport
