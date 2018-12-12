"""Warpgate policy server.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import ipaddress  # pylint: disable=wrong-import-order
import json
import logging
import os
import random
from urllib import parse as urlparse

from twisted.internet import protocol

from treadmill import fs
from treadmill import netdev
from treadmill import vipfile
from treadmill.gssapiprotocol import jsonserver

from . import _utils

_LOGGER = logging.getLogger(__name__)


class WarpgatePolicyServer(jsonserver.GSSAPIJsonServer):
    """Warpgate policy server."""

    __slots__ = (
        '_endpoint_dev',
        '_endpoint_ip',
        '_networks',
        '_session',
        '_policies_dir',
        '_sessions_dir',
    )

    def __init__(self, endpoint_dev, endpoint_ip,
                 policies_dir, networks, state_dir):
        super().__init__()
        self._endpoint_dev = endpoint_dev
        self._endpoint_ip = endpoint_ip
        self._networks = networks
        self._policies_dir = policies_dir
        self._session = None
        self._sessions_dir = os.path.join(state_dir, 'sessions')

    def on_request(self, request):
        """Process policy request.
        """
        peer = self.peer()
        # TODO: Validate request
        policy_name = request['policy']
        # TODO: Isn't there a way to do thing through Twisted?
        laddr = self.transport.socket.getsockname()
        raddr = self.transport.socket.getpeername()
        _LOGGER.debug('Warpgate cnx: %r <-> %r', laddr, raddr)

        reply = self._process_request(
            client_principal=peer,
            client_addr=raddr[0],
            policy_name=policy_name
        )

        return reply

    def connectionLost(self, reason=protocol.connectionDone):
        """Handle a disconnect from a client.
        """
        super().connectionLost(reason)
        session = self._session
        if session is not None:
            _LOGGER.info('Terminating session %08x', session['id'])
            _utils.wg_dev_delete(session['interface'])
            session_name = _session_fname(session)
            session_network = self._networks[session['network']]
            session_network['pool'].free(
                owner=session_name,
                owned_ip=session['client_ip']
            )
            fs.rm_safe(
                os.path.join(self._sessions_dir, session_name)
            )
            self._session = None

    def _process_request(self, client_principal, client_addr, policy_name):
        """Process a single request.
        """
        # XXX: Add error handling?
        _LOGGER.info('Request %r:%r (from %r)',
                     client_principal, policy_name, client_addr)

        # See if we have a policy. We use the client_principal as namespace for
        # the policy lookup.
        namespace = urlparse.quote(client_principal.lower(), safe='@')
        # Create a session
        session = _get_policy(
            repository=self._policies_dir,
            namespace=namespace,
            name=policy_name
        )
        if not session:
            _LOGGER.warning('Nonexistent session %r', policy_name)
            return {
                '_error': 'no session'
            }
        # XXX: Find a better scheme to select session id
        session['id'] = random.randint(0, (2**32) - 1)

        session_name = _session_fname(session)

        # Assign an IP from the network
        gateway_ip = None
        network_idx = None
        for cidr, network in self._networks.items():
            try:
                client_ip = network['pool'].alloc(session_name)
            except Exception:  # pylint: disable=broad-except
                # FIXME: add proper exception handling
                continue
            gateway_ip = network['gateway_ip']
            network_cidr = cidr
            break
        else:
            _LOGGER.critical('Could not assign an IP for %r', session_name)
            return {
                '_error': 'no capacity'
            }

        # Setup the interface
        tun_devname = _utils.wg_dev_create(
            unique_id=session['id'],
            tun_localaddr=gateway_ip,
            tun_remoteaddr=client_ip,
            ll_devname=self._endpoint_dev,
            ll_localaddr=self._endpoint_ip,
            ll_remoteaddr=client_addr
        )
        session['interface'] = tun_devname
        session['client_ip'] = client_ip
        session['gateway_ip'] = gateway_ip
        session['network'] = network_cidr

        # Setup the firewall XXX
        # Enable forwarding
        netdev.dev_conf_forwarding_set(tun_devname, True)

        self._session = session
        with open(os.path.join(self._sessions_dir, session_name), 'w') as f:
            json.dump(session, fp=f, indent=4)

        # Bring up the interface
        netdev.link_set_up(tun_devname)

        # The reply contains the reverse tunnel settings for the client
        return {
            'local_ip': client_ip,
            'remote_ip': gateway_ip,
            'endpoint_ip': self._endpoint_ip,
            'routes': session['routes'],
            'endpoints': session['endpoints'],
            'session_id': session['id'],
        }


class WarpgatePolicyServerFactory(protocol.Factory):
    """Warpgate policy server factory."""

    __slots__ = (
        '_endpoint_dev',
        '_endpoint_ip',
        '_networks',
        '_policies_dir',
        '_state_dir',
    )

    def __init__(self, tun_cidrs,
                 endpoint_dev, endpoint_ip,
                 policies_dir, state_dir):
        """
        """
        super().__init__()
        self._endpoint_dev = endpoint_dev
        self._endpoint_ip = endpoint_ip
        self._policies_dir = policies_dir
        self._state_dir = state_dir
        fs.mkdir_safe(state_dir)

        self._networks = _init_networks(self._state_dir, tun_cidrs)
        # Now that the network routes (blackhost) are enabled, we can enable
        # forwarding.
        netdev.dev_conf_forwarding_set(endpoint_dev, True)

        _LOGGER.debug('Initialized')

    def buildProtocol(self, addr):
        """Create a server from a connected client.
        """
        return WarpgatePolicyServer(
            endpoint_dev=self._endpoint_dev,
            endpoint_ip=self._endpoint_ip,
            policies_dir=self._policies_dir,
            networks=self._networks,
            state_dir=self._state_dir,
        )


def _session_fname(session):
    session_name = '{namespace}-{name}-{id:08x}'.format(
        namespace=session['namespace'],
        name=session['name'],
        id=session['id']
    )
    return session_name


def _init_networks(state_dir, cidrs):
    """Initializes a CIDR for usage by the Warpgate server.
    """
    vips_path = os.path.join(state_dir, 'vips')
    sessions_path = os.path.join(state_dir, 'sessions')
    fs.mkdir_safe(sessions_path)

    # Clean up old sessions
    for old_session in os.listdir(sessions_path):
        _LOGGER.info('Cleaning up old session %r', old_session)
        os.unlink(os.path.join(sessions_path, old_session))

    # Clean up old interfaces
    for old_devname in _utils.wg_dev_list():
        _LOGGER.info('Cleaning up old device %r', old_devname)
        _utils.wg_dev_delete(old_devname)

    networks = {}
    for cidr in cidrs:
        _LOGGER.debug('Setting up %r', cidr)
        pool = vipfile.VipMgr(
            cidr=cidr,
            path=vips_path,
            owner_path=sessions_path
        )
        pool.initialize()
        wg_ip = pool.alloc('self')  # XXX: Point to self
        # blackhole all the managed network ranges
        try:
            netdev.route_add(cidr, rtype='blackhole')
        except netdev.subproc.CalledProcessError as err:
            if err.returncode == 2:  # route already exists
                pass
            else:
                raise
        networks[cidr] = {
            'gateway_ip': wg_ip,
            'pool': pool
        }

    return networks


def _get_policy(repository, namespace, name):
    """Read and return the requested policy's data or None if not found.
    """
    # TODO: add basic sanity checks to namespace / policy name
    try:
        policy_filename = os.path.join(
            repository,
            'policies',
            namespace,
            os.path.extsep.join([name, 'json'])
        )
        with open(policy_filename) as policy_file:
            policy = json.load(fp=policy_file)
        _LOGGER.info('Loaded policy from %r', policy_filename)
    except FileNotFoundError:
        return None

    # Load networks definitions
    netdefs_dir = os.path.join(repository, 'networks')
    networks = {}
    for netdef in os.listdir(netdefs_dir):
        try:
            with open(os.path.join(netdefs_dir, netdef)) as netdef_file:
                data = json.load(fp=netdef_file)
        except FileNotFoundError:
            continue
        # XXX: Create jsonschemas for policy / definitions
        if not isinstance(data, list):
            _LOGGER.warning('Invalid network definition: %r', netdef)
            continue
        network, _, _ = netdef.rpartition(os.path.extsep)
        networks[network] = data
    # Expand routes
    final_routes = []
    for route in policy['routes']:
        try:
            ipaddress.IPv4Network(route)
            final_routes.append(route)
            continue
        except ipaddress.AddressValueError:
            # This is not an CIDR notation route, search network defs.
            if route in networks:
                final_routes.extend(networks[route])
                _LOGGER.info('Loaded network %r for %r',
                             route, name)
            else:
                KeyError('Invalid route: %r' % route)
    policy['routes'] = final_routes
    # Normalize endpoints.
    policy['endpoints'] = policy.get('endpoints', [])
    # Record namespace in policy
    policy['namespace'] = namespace
    policy['name'] = name
    return policy


def run_server(admin_address, admin_port, tun_devname, tun_address, tun_cidrs,
               state_dir, policies_dir):
    """Runs warpgate server.
    """
    from twisted.internet import reactor

    _LOGGER.info('Warpgate server starting.')

    listener = reactor.listenTCP(
        port=admin_port,
        factory=WarpgatePolicyServerFactory(
            tun_cidrs=tun_cidrs,
            endpoint_dev=tun_devname,
            endpoint_ip=tun_address,
            policies_dir=policies_dir,
            state_dir=state_dir
        ),
        backlog=100,
        interface=admin_address
    )
    addr = listener.getHost()
    _LOGGER.info('Warpgate policy server listening on %s:%s',
                 addr.host, addr.port)

    reactor.run()


__all__ = [
    'run_server',
]
