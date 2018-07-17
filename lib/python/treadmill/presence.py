"""Reports presence information into Zookeeper.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import time
import logging
import sys

import kazoo

from treadmill import exc
from treadmill import sysinfo
from treadmill import zkutils

from treadmill import zknamespace as z

from treadmill.appcfg import abort as app_abort


_LOGGER = logging.getLogger(__name__)

_INVALID_IDENTITY = sys.maxsize

# Time to wait when registering endpoints in case previous ephemeral
# endpoint is still present.
_EPHEMERAL_RETRY_INTERVAL = 5
_EPHEMERAL_RETRY_COUNT = 13


def _create_ephemeral_with_retry(zkclient, path, data):
    """Create ephemeral node with retry."""
    prev_data = None
    acl = zkclient.make_servers_acl()
    for _ in range(0, _EPHEMERAL_RETRY_COUNT):
        try:
            return zkutils.create(zkclient, path, data, acl=[acl],
                                  ephemeral=True)
        except kazoo.client.NodeExistsError:
            prev_data = zkutils.get_default(zkclient, path)
            _LOGGER.warning(
                'Node exists, will retry: %s, data: %r',
                path, prev_data
            )
            time.sleep(_EPHEMERAL_RETRY_INTERVAL)

    raise exc.ContainerSetupError('%s:%s' % (path, prev_data),
                                  app_abort.AbortedReason.PRESENCE)


class EndpointPresence:
    """Manages application endpoint registration in Zookeeper."""

    def __init__(self, zkclient, manifest, hostname=None, appname=None):
        self.zkclient = zkclient
        self.manifest = manifest
        self.hostname = hostname if hostname else sysinfo.hostname()
        if appname:
            self.appname = appname
        else:
            self.appname = self.manifest.get('name')

    def register(self):
        """Register container in Zookeeper."""
        self.register_identity()
        self.register_running()
        self.register_endpoints()

    def register_running(self):
        """Register container as running."""
        _LOGGER.info('registering container as running: %s', self.appname)
        _create_ephemeral_with_retry(self.zkclient,
                                     z.path.running(self.appname),
                                     self.hostname)

    def unregister_running(self):
        """Safely deletes the "running" node for the container."""
        _LOGGER.info('un-registering container as running: %s', self.appname)
        path = z.path.running(self.appname)
        try:
            data, _metadata = self.zkclient.get(path)
            if data and data.decode() == self.hostname:
                self.zkclient.delete(path)
        except kazoo.client.NoNodeError:
            _LOGGER.info('running node does not exist.')

    def register_endpoints(self):
        """Registers service endpoint."""
        _LOGGER.info('registering endpoints: %s', self.appname)

        endpoints = self.manifest.get('endpoints', [])
        for endpoint in endpoints:
            internal_port = endpoint['port']
            ep_name = endpoint.get('name', str(internal_port))
            ep_port = endpoint['real_port']
            ep_proto = endpoint.get('proto', 'tcp')

            hostport = self.hostname + ':' + str(ep_port)
            path = z.path.endpoint(self.appname, ep_proto, ep_name)
            _LOGGER.info('register endpoint: %s %s', path, hostport)

            # Endpoint node is created with default acl. It is ephemeral
            # and not supposed to be modified by anyone.
            _create_ephemeral_with_retry(self.zkclient, path, hostport)

    def unregister_endpoints(self):
        """Unregisters service endpoint."""
        _LOGGER.info('registering endpoints: %s', self.appname)

        endpoints = self.manifest.get('endpoints', [])
        for endpoint in endpoints:
            port = endpoint.get('port', '')
            ep_name = endpoint.get('name', str(port))
            ep_proto = endpoint.get('proto', 'tcp')

            if not ep_name:
                _LOGGER.critical('Logic error, no endpoint info: %s',
                                 self.manifest)
                return

            path = z.path.endpoint(self.appname, ep_proto, ep_name)
            _LOGGER.info('un-register endpoint: %s', path)
            try:
                data, _metadata = self.zkclient.get(path)
                if data and data.decode().split(':')[0] == self.hostname:
                    self.zkclient.delete(path)
            except kazoo.client.NoNodeError:
                _LOGGER.info('endpoint node does not exist.')

    def register_identity(self):
        """Register app identity."""
        identity_group = self.manifest.get('identity_group')

        # If identity_group is not set or set to None, nothing to register.
        if not identity_group:
            return

        identity = self.manifest.get('identity', _INVALID_IDENTITY)

        _LOGGER.info('Register identity: %s, %s', identity_group, identity)
        _create_ephemeral_with_retry(
            self.zkclient,
            z.path.identity_group(identity_group, str(identity)),
            {'host': self.hostname, 'app': self.appname},
        )

    def unregister_identity(self):
        """Register app identity."""
        identity_group = self.manifest.get('identity_group')

        # If identity_group is not set or set to None, nothing to register.
        if not identity_group:
            return

        identity = self.manifest.get('identity', _INVALID_IDENTITY)

        _LOGGER.info('Unregister identity: %s, %s', identity_group, identity)
        path = z.path.identity_group(identity_group, str(identity))
        try:
            data = zkutils.get(self.zkclient, path)
            if data['host'] == self.hostname:
                zkutils.ensure_deleted(self.zkclient, path)
        except kazoo.client.NoNodeError:
            _LOGGER.info('identity node %s does not exist.', path)


def server_node(hostname, presence_id):
    """Return server.presence node for given hostname and presence_id."""
    if presence_id == '-1':
        return hostname
    return '{}#{}'.format(hostname, presence_id)


def parse_server(node):
    """Return hostname and presence_id for given server.presence node."""
    if '#' not in node:
        return node, '-1'
    hostname, presence_id = node.split('#')
    return hostname, presence_id


def server_hostname(node):
    """Return hostname for given server.presence node."""
    return parse_server(node)[0]


def find_server(zkclient, hostname):
    """Find server."""
    for node in sorted(zkclient.get_children(z.SERVER_PRESENCE), reverse=True):
        if server_hostname(node) == hostname:
            return z.path.server_presence(node)
    return None


def register_server(zkclient, hostname, node_info):
    """Register server."""
    server_path = z.path.server(hostname)

    server_data = zkutils.get(zkclient, server_path)
    server_data.update(node_info)

    _LOGGER.info('Registering server %s: %r', hostname, server_data)

    zkutils.update(zkclient, server_path, server_data)

    host_acl = zkclient.make_host_acl(hostname, 'rwcda')
    return zkutils.put(
        zkclient, z.path.server_presence(hostname + '#'), {'seen': False},
        acl=[host_acl], ephemeral=True, sequence=True
    )


def unregister_server(zkclient, hostname):
    """Unregister server."""
    _LOGGER.info('Unregistering server %s', hostname)
    server_presence_path = find_server(zkclient, hostname)
    if server_presence_path:
        zkutils.ensure_deleted(zkclient, server_presence_path)


def kill_node(zkclient, node):
    """Kills app, endpoints, and server node."""
    _LOGGER.info('killing node: %s', node)
    try:
        zkutils.get(zkclient, z.path.server(node))
    except kazoo.client.NoNodeError:
        _LOGGER.info('node does not exist.')
        return

    apps = zkclient.get_children(z.path.placement(node))
    for app in apps:
        _LOGGER.info('removing app presence: %s', app)
        try:
            manifest = zkutils.get(zkclient, z.path.scheduled(app))
            app_presence = EndpointPresence(zkclient,
                                            manifest,
                                            hostname=node,
                                            appname=app)
            app_presence.unregister_running()
            app_presence.unregister_endpoints()
        except kazoo.client.NoNodeError:
            _LOGGER.info('app %s no longer scheduled.', app)

    _LOGGER.info('removing server presence: %s', node)
    unregister_server(zkclient, node)
