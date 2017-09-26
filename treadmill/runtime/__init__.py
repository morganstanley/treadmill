"""Treadmill runtime framework.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import json
import logging
import os
import random
import socket
import stat

import six

from treadmill import exc
from treadmill import fs
from treadmill import utils
from treadmill import plugin_manager

from treadmill.appcfg import abort as app_abort
from treadmill.appcfg import manifest as app_manifest


STATE_JSON = 'state.json'

_LOGGER = logging.getLogger(__name__)

_RUNTIME_NAMESPACE = 'treadmill.runtime'


if os.name == 'posix':
    # Disable C0413: should be placed at the top of the module.
    from treadmill import iptables  # pylint: disable=c0413
    PORT_SPAN = iptables.PORT_SPAN
    PROD_PORT_LOW = iptables.PROD_PORT_LOW
    PROD_PORT_HIGH = iptables.PROD_PORT_HIGH
    NONPROD_PORT_LOW = iptables.NONPROD_PORT_LOW
    NONPROD_PORT_HIGH = iptables.NONPROD_PORT_HIGH
else:
    PORT_SPAN = 8192
    PROD_PORT_LOW = 32768
    PROD_PORT_HIGH = PROD_PORT_LOW + PORT_SPAN - 1
    NONPROD_PORT_LOW = PROD_PORT_LOW + PORT_SPAN
    NONPROD_PORT_HIGH = NONPROD_PORT_LOW + PORT_SPAN - 1


def get_runtime(runtime_name, tm_env, container_dir):
    """Gets the runtime implementation with the given name."""
    try:
        runtime_cls = plugin_manager.load(_RUNTIME_NAMESPACE, runtime_name)
        return runtime_cls(tm_env, container_dir)
    except KeyError:
        _LOGGER.error('Runtime not supported: %s', runtime_name)


def load_app(container_dir, app_json=STATE_JSON):
    """Load app from original manifest."""
    manifest_file = os.path.join(container_dir, app_json)

    try:
        manifest = app_manifest.read(manifest_file)
        _LOGGER.debug('Manifest: %r', manifest)
        return utils.to_obj(manifest)

    except IOError as err:
        if err.errno != errno.ENOENT:
            raise

        _LOGGER.critical('Manifest file does not exist: %r', manifest_file)
        return None


def save_app(manifest, container_dir, app_json=STATE_JSON):
    """Saves app manifest and freezes to object."""
    # Save the manifest with allocated vip and ports in the state
    state_file = os.path.join(container_dir, app_json)
    fs.write_safe(
        state_file,
        lambda f: json.dump(manifest, f)
    )
    # chmod for the file to be world readable.
    if os.name == 'posix':
        os.chmod(
            state_file,
            stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
        )

    # Freeze the app data into a namedtuple object
    return utils.to_obj(manifest)


def _allocate_sockets(environment, host_ip, sock_type, count):
    """Return a list of `count` socket bound to an ephemeral port.
    """
    # TODO: this should probably be abstracted away
    if environment == 'prod':
        port_pool = six.moves.range(PROD_PORT_LOW, PROD_PORT_HIGH + 1)
    else:
        port_pool = six.moves.range(NONPROD_PORT_LOW, NONPROD_PORT_HIGH + 1)

    port_pool = random.sample(port_pool, PORT_SPAN)

    # socket objects are closed on GC so we need to return
    # them and expect the caller to keep them around while needed
    sockets = []

    for real_port in port_pool:
        if len(sockets) == count:
            break

        socket_ = socket.socket(socket.AF_INET, sock_type)
        try:
            socket_.bind((host_ip, real_port))
            if sock_type == socket.SOCK_STREAM:
                socket_.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                socket_.listen(0)
        except socket.error as err:
            if err.errno == errno.EADDRINUSE:
                continue
            raise

        sockets.append(socket_)
    else:
        raise exc.ContainerSetupError('{0} < {1}'.format(len(sockets), count),
                                      app_abort.AbortedReason.PORTS)

    return sockets


def _allocate_network_ports_proto(host_ip, manifest, proto, so_type):
    """Allocate ports for named and unnamed endpoints given protocol."""
    ephemeral_count = manifest['ephemeral_ports'].get(proto, 0)

    endpoints = [ep for ep in manifest['endpoints']
                 if ep.get('proto', 'tcp') == proto]
    endpoints_count = len(endpoints)

    sockets = _allocate_sockets(
        manifest['environment'],
        host_ip,
        so_type,
        endpoints_count + ephemeral_count
    )

    for idx, endpoint in enumerate(endpoints):
        sock = sockets[idx]
        endpoint['real_port'] = sock.getsockname()[1]

        # Specifying port 0 tells appmgr that application wants to
        # have same numeric port value in the container and in
        # the public interface.
        #
        # This is needed for applications that advertise ports they
        # listen on to other members of the app/cluster.
        if endpoint['port'] == 0:
            endpoint['port'] = endpoint['real_port']

    # Ephemeral port are the rest of the ports
    manifest['ephemeral_ports'][proto] = [
        sock.getsockname()[1]
        for sock in sockets[endpoints_count:]
    ]

    return sockets


def allocate_network_ports(host_ip, manifest):
    """Allocate ports for named and unnamed endpoints.

    :returns:
        ``list`` of bound sockets
    """
    tcp_sockets = _allocate_network_ports_proto(host_ip,
                                                manifest,
                                                'tcp',
                                                socket.SOCK_STREAM)
    udp_sockets = _allocate_network_ports_proto(host_ip,
                                                manifest,
                                                'udp',
                                                socket.SOCK_DGRAM)
    return tcp_sockets + udp_sockets
