"""Presence management service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import logging
import sys

import kazoo

from treadmill import appcfg
from treadmill import context
from treadmill import logcontext as lc
from treadmill import zkutils
from treadmill import zknamespace as z
from treadmill import sysinfo
from treadmill import utils

from . import BaseResourceServiceImpl

_LOGGER = logging.getLogger(__name__)

_INVALID_IDENTITY = sys.maxsize


class PresenceResourceService(BaseResourceServiceImpl):
    """Presence service implementation.
    """

    __slots__ = (
        'hostname',
        'presence',
    )

    PAYLOAD_SCHEMA = (('endpoints', True, list),
                      ('identity', False, int),
                      ('identity_group', False, str))

    def __init__(self):
        super(PresenceResourceService, self).__init__()
        self.hostname = sysinfo.hostname()
        self.presence = collections.defaultdict(dict)

    @property
    def zkclient(self):
        """Lazily creates Zookeeper client.
        """
        return context.GLOBAL.zk.conn

    def initialize(self, service_dir):
        super(PresenceResourceService, self).initialize(service_dir)
        session_id, _pwd = self.zkclient.client_id
        _LOGGER.info('Presence service initialized: %s, session id: %s',
                     service_dir, session_id)

    def synchronize(self):
        pass

    def report_status(self):
        return {'ready': True}

    def event_handlers(self):
        return []

    def on_create_request(self, rsrc_id, rsrc_data):

        with lc.LogContext(_LOGGER, rsrc_id,
                           adapter_cls=lc.ContainerAdapter) as log:
            log.info('Creating presence: %s', rsrc_data)
            app_name = appcfg.app_name(rsrc_id)

            # Register running.
            path = z.path.running(app_name)
            _LOGGER.info('Register running: %s, %s', path, self.hostname)
            if not self._safe_create(rsrc_id, path, self.hostname):
                _LOGGER.info('Waiting to expire: %s', path)
                return None

            self.presence[app_name][path] = rsrc_id

            # Register endpoints.
            for endpoint in rsrc_data.get('endpoints', []):
                internal_port = endpoint['port']
                ep_name = endpoint.get('name', str(internal_port))
                ep_port = endpoint['real_port']
                ep_proto = endpoint.get('proto', 'tcp')

                hostport = self.hostname + ':' + str(ep_port)

                path = z.path.endpoint(app_name, ep_proto, ep_name)
                _LOGGER.info('Register endpoint: %s, %s', path, hostport)
                if not self._safe_create(rsrc_id, path, hostport):
                    _LOGGER.info('Waiting to expire: %s', path)
                    return None

                self.presence[app_name][path] = rsrc_id

            # Register identity.
            identity_group = rsrc_data.get('identity_group')
            if identity_group:
                identity = rsrc_data.get('identity', _INVALID_IDENTITY)
                identity_data = {'host': self.hostname, 'app': app_name}

                path = z.path.identity_group(identity_group, str(identity))
                _LOGGER.info('Register identity: %s, %s', path, identity_data)
                if not self._safe_create(rsrc_id, path, identity_data):
                    _LOGGER.info('Waiting to expire: %s', path)
                    return None

                self.presence[app_name][path] = rsrc_id

        return {}

    def on_delete_request(self, rsrc_id):
        with lc.LogContext(_LOGGER, rsrc_id,
                           adapter_cls=lc.ContainerAdapter) as log:
            log.info('Deleting presence')
            app_name = appcfg.app_name(rsrc_id)

            to_delete = [
                path for path in self.presence[app_name]
                if self.presence[app_name][path] == rsrc_id
            ]

            for path in to_delete:
                self._safe_delete(path)
                del self.presence[app_name][path]

            if not self.presence[app_name]:
                del self.presence[app_name]

        return True

    def _watch(self, rsrc_id, path):
        """Retry request when path is deleted."""
        @self.zkclient.DataWatch(path)
        @utils.exit_on_unhandled
        def _retry_request(data, _stat, event):
            """Force exit if server node is deleted."""
            if (data is None or
                    (event is not None and event.type == 'DELETED')):
                # The node is deleted, safe to retry request.
                self.retry_request(rsrc_id)
                return False
            else:
                return True

    def _safe_create(self, rsrc_id, path, data):
        """Create ephemeral node in Zookeeper.

        If the node is present, check if the owner session id is ours, if not,
        fail.
        """
        acl = self.zkclient.make_servers_acl()

        try:
            zkutils.create(
                self.zkclient, path, data, acl=[acl], ephemeral=True
            )
            _LOGGER.info('Created node: %s', path)
        except kazoo.client.NodeExistsError:
            try:
                content, metadata = zkutils.get_with_metadata(
                    self.zkclient, path
                )
            except kazoo.client.NoNodeError:
                # The node existed when we tried to create, but now it is gone.
                self.retry_request(rsrc_id)
                return False
            session_id, _pwd = self.zkclient.client_id
            if metadata.owner_session_id != session_id:
                _LOGGER.info('Node exists, owned by other: %s - %s - %s',
                             path,
                             content,
                             metadata.owner_session_id)
                self._watch(rsrc_id, path)
                return False

            if content != data:
                _LOGGER.info('Content different: %s - old: %s, new: %s',
                             path, content, data)
                zkutils.update(self.zkclient, path, data)

            _LOGGER.info('Node is up to date: %s - %s', path, session_id)

        return True

    def _safe_delete(self, path):
        """Safely delete node, checking that it is owned by the service."""
        try:
            _content, metadata = zkutils.get_with_metadata(self.zkclient, path)
            session_id, _pwd = self.zkclient.client_id
            if metadata.owner_session_id == session_id:
                _LOGGER.info('Delete node: %s', path)
                zkutils.ensure_deleted(self.zkclient, path)
            else:
                _LOGGER.info('Node exists, owned by other: %s - %s',
                             path, metadata.owner_session_id)
        except kazoo.client.NoNodeError:
            _LOGGER.info('Node does not exist: %s', path)
