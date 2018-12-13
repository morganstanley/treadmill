"""Warpgate client
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import socket

from treadmill import netdev

from . import _utils

_LOGGER = logging.getLogger(__name__)


def _apply_policy(policy, devname, devaddr):
    """Create network interfaces, routes and firewall rules per policy.

    :param `str` devname:
        Local device name to use for the tunnel.
    :param `str` devaddr:
        IP address to use on the local device for the tunnel.
    """
    tun_devname = _utils.wg_dev_create(
        unique_id=policy['session_id'],
        tun_localaddr=policy['local_ip'],
        tun_remoteaddr=policy['remote_ip'],
        ll_devname=devname,
        ll_localaddr=devaddr,
        ll_remoteaddr=policy['endpoint_ip'],
    )
    # Add firewall rules.
    _utils.wg_firewall_client_init(tun_devname, policy['endpoints'])
    # No traffic should be *routed* from the WarpGate interface.
    netdev.dev_conf_forwarding_set(tun_devname, False)
    # Bring up the device.
    netdev.link_set_up(tun_devname)
    # Add routes found in the policy
    _utils.wg_route_create(
        tun_devname,
        policy['local_ip'],
        policy['remote_ip'],
        policy['routes']
    )


def _init_network():
    """Re-initialize the network environment.
    """
    # Clean up old interfaces
    for old_devname in _utils.wg_dev_list():
        _LOGGER.info('Cleaning up old device %r', old_devname)
        _utils.wg_dev_delete(old_devname)
        _utils.wg_firewall_client_fini(old_devname)
    # Setup firewall fundations
    _utils.wg_firewall_client_init_once()


def run_client(policy_servers, service_principal, policy_name,
               tun_dev, tun_addr):
    """Run the WarpGate client.

    :param `list` policy_servers:
        List of WarpGate policy servers to try to connect to (in order).
    :param `str` service_principal:
        Kerberos service principal of the WarpGate servers.
    :param `str` policy name:
        Name of the policy to request.
    :param `str` tun_dev:
        Local device name to use for the tunnel.
    :param `str` tun_addr:
        IP address to use on the local device for the tunnel.
    """
    from treadmill.gssapiprotocol import jsonclient

    _init_network()

    # Establish connection to the policy server and keep it open.
    #
    # Disconnecting from the policy server will retry with the next in the
    # list. If all fail, exit.
    #
    # In case policy servers change in Zookeeper, process will restart by
    # the supervisor, and re-evaluate.
    nb_retries = 0
    while 0 <= nb_retries < len(policy_servers):
        for hostport in policy_servers:
            host, port = hostport.split(':')
            port = int(port)
            principal = '{}@{}'.format(service_principal, host)

            _LOGGER.info('Connecting to %s on %s:%s', principal, host, port)
            client = jsonclient.GSSAPIJsonClient(
                host, port, principal
            )
            try:
                if not client.connect():
                    nb_retries += 1
                    continue

                # We connected
                nb_retries = 0

                # Request the policy
                client.write_json(
                    {
                        'policy': policy_name
                    }
                )
                policy = client.read_json()
                _LOGGER.info('Policy[%s]: %r', policy_name, policy)
                # TODO: Validate policy response.
                if '_error' in policy:
                    # TODO: handle temporary(fail) vs permanent(denied)
                    #       failures. For now, always abort
                    nb_retries = -1
                    break

                _apply_policy(policy, tun_dev, tun_addr)

                # This will block, holding the connection.
                wait_for_reply = client.read()
                if wait_for_reply is None:
                    continue
            except socket.error as sock_err:
                _LOGGER.warning('Exception connecting to %s:%s - %s',
                                host, port, sock_err)


__all__ = [
    'run_client',
]
