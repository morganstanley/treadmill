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

# ACL which allows all servers in the cell to full control over node.
#
# Set in /finished, /servers
_SERVERS_ACL = zkutils.make_role_acl('servers', 'rwcda')
# Delete only servers ACL
_SERVERS_ACL_DEL = zkutils.make_role_acl('servers', 'd')


class ZkReadonlyBackend(backend.Backend):
    """Implements readonly Zookeeper based storage."""

    def __init__(self, zkclient):
        self.zkclient = zkclient
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

    def exists(self, path):
        """Check if object exists."""
        try:
            return self.zkclient.exists(path)
        except kazoo.client.NoNodeError:
            raise backend.ObjectNotFoundError()


class ZkBackend(ZkReadonlyBackend):
    """Implements RW Zookeeper storage."""

    def __init__(self, zkclient):
        super(ZkBackend, self).__init__(zkclient)
        self.acls = {
            '/': None,
            z.ALLOCATIONS: None,
            z.APPMONITORS: None,
            z.BUCKETS: None,
            z.CELL: None,
            z.IDENTITY_GROUPS: None,
            z.PLACEMENT: None,
            z.PARTITIONS: None,
            z.SCHEDULED: [_SERVERS_ACL_DEL],
            z.SCHEDULER: None,
            z.SERVERS: None,
            z.STATE_REPORTS: None,
            z.STRATEGIES: None,
            z.FINISHED: [_SERVERS_ACL],
            z.FINISHED_HISTORY: None,
            z.TRACE: None,
            z.TRACE_HISTORY: None,
            z.VERSION_ID: None,
            z.ZOOKEEPER: None,
            z.BLACKEDOUT_SERVERS: [_SERVERS_ACL],
            z.ENDPOINTS: [_SERVERS_ACL],
            z.path.endpoint_proid('root'): [_SERVERS_ACL],
            z.EVENTS: [_SERVERS_ACL],
            z.RUNNING: [_SERVERS_ACL],
            z.SERVER_PRESENCE: [_SERVERS_ACL],
            z.VERSION: [_SERVERS_ACL],
            z.VERSION_HISTORY: [_SERVERS_ACL],
            z.REBOOTS: [_SERVERS_ACL],
        }

        for path in z.trace_shards():
            self.acls[path] = [_SERVERS_ACL]

    def _acl(self, path):
        """Returns ACL of the Zookeeper node."""
        if path in self.acls:
            return self.acls[path]

        if path.startswith(z.path.placement('')):
            return [_SERVERS_ACL]

        if path.startswith(z.path.reboot('')):
            return [_SERVERS_ACL_DEL]

        if path.startswith(z.path.finished('')):
            return [_SERVERS_ACL]

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
