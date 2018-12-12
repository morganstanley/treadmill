"""Zookeeper scheduler/master backend.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import kazoo

from treadmill import zknamespace as z
from treadmill import zkutils

from . import backend

_LOGGER = logging.getLogger(__name__)


class ZkReadonlyBackend(backend.Backend):
    """Implements readonly Zookeeper based storage."""

    def __init__(self, zkclient):
        self.zkclient = zkclient
        # pylint: disable=C0103
        self.ChildrenWatch = self.zkclient.ChildrenWatch
        super(ZkReadonlyBackend, self).__init__()

    def list(self, path):
        """Return path listing."""
        try:
            return self.zkclient.get_children(path)
        except kazoo.client.NoNodeError:
            raise backend.ObjectNotFoundError()

    def get_default(self, path, default=None):
        """Return stored object or default if not found."""
        return zkutils.get_default(self.zkclient, path, default=default)

    def get(self, path):
        """Return stored object given path."""
        try:
            return zkutils.get(self.zkclient, path)
        except kazoo.client.NoNodeError:
            raise backend.ObjectNotFoundError()

    def get_with_metadata(self, path):
        """Return stored object with metadata."""
        try:
            return zkutils.get_with_metadata(self.zkclient, path)
        except kazoo.client.NoNodeError:
            raise backend.ObjectNotFoundError()

    def exists(self, path):
        """Check if object exists."""
        try:
            return self.zkclient.exists(path)
        except kazoo.client.NoNodeError:
            raise backend.ObjectNotFoundError()

    def event_object(self):
        """Create new event object."""
        return self.zkclient.handler.event_object()

    def delete(self, path):
        _LOGGER.debug('delete %r', path)

    def ensure_exists(self, path):
        _LOGGER.debug('ensure_exists %r', path)

    def put(self, path, value):
        _LOGGER.debug('put %r: %r', path, value)

    def update(self, path, data, check_content=False):
        _LOGGER.debug('update %r: %r', path, data)


class ZkBackend(ZkReadonlyBackend):
    """Implements RW Zookeeper storage."""

    def __init__(self, zkclient):
        super(ZkBackend, self).__init__(zkclient)
        servers_acl = zkclient.make_servers_acl()
        servers_del_acl = zkclient.make_servers_del_acl()
        self.acls = {
            '/': None,
            z.ALLOCATIONS: None,
            z.APPMONITORS: None,
            z.BUCKETS: None,
            z.CELL: None,
            z.DISCOVERY: [servers_acl],
            z.DISCOVERY_STATE: [servers_acl],
            z.IDENTITY_GROUPS: None,
            z.PLACEMENT: None,
            z.PARTITIONS: None,
            z.SCHEDULED: [servers_del_acl],
            z.SCHEDULED_STATS: None,
            z.SCHEDULER: None,
            z.SERVERS: None,
            z.STATE_REPORTS: None,
            z.STRATEGIES: None,
            z.FINISHED: [servers_acl],
            z.FINISHED_HISTORY: None,
            z.TRACE: None,
            z.TRACE_HISTORY: None,
            z.VERSION_ID: None,
            z.ZOOKEEPER: None,
            z.BLACKEDOUT_SERVERS: [servers_acl],
            z.ENDPOINTS: [servers_acl],
            z.path.endpoint_proid('root'): [servers_acl],
            z.EVENTS: [servers_acl],
            z.RUNNING: [servers_acl],
            z.SERVER_PRESENCE: [servers_acl],
            z.VERSION: [servers_acl],
            z.VERSION_HISTORY: [servers_acl],
            z.REBOOTS: [servers_acl],
        }

        for path in z.trace_shards():
            self.acls[path] = [servers_acl]

        for path in z.server_trace_shards():
            self.acls[path] = [servers_acl]

    def _acl(self, path):
        """Returns ACL of the Zookeeper node."""
        if path in self.acls:
            return self.acls[path]

        if path.startswith(z.path.placement('')):
            return [self.zkclient.make_servers_acl()]

        if path.startswith(z.path.reboot('')):
            return [self.zkclient.make_servers_del_acl()]

        if path.startswith(z.path.finished('')):
            return [self.zkclient.make_servers_acl()]

        return None

    def put(self, path, value):
        """Store object at a given path."""
        return zkutils.put(self.zkclient, path, value, acl=self._acl(path))

    def ensure_exists(self, path):
        """Ensure storage path exists."""
        return zkutils.ensure_exists(self.zkclient, path, acl=self._acl(path))

    def delete(self, path):
        """Delete object given the path."""
        return zkutils.ensure_deleted(self.zkclient, path)

    def update(self, path, data, check_content=False):
        """Set data into ZK node."""
        try:
            zkutils.update(self.zkclient, path, data, check_content)
        except kazoo.client.NoNodeError:
            raise backend.ObjectNotFoundError()
