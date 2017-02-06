"""Manage a port-redirect ring between Treadmill containers.

Each vring manages chain of iptables output rules, which enables applications
that expect to find their peers on a "well-defined" constant port to be
deployed inside the container.
"""


import logging
import socket

from . import firewall
from . import iptables


_LOGGER = logging.getLogger(__name__)


def init(ring):
    """Creates an iptable chain for the vring."""
    iptables.create_chain('nat', ring)
    jumprule = '-j %s' % ring
    iptables.add_raw_rule('nat', iptables.OUTPUT, jumprule, safe=True)


def run(ring, routing, endpoints, discovery):
    """Manage ring rules based on discovery info.

    :param routing:
        The map between logical endpoint name and internal container port that
        is used for this endpoint.
    :param endpoints:
        The set of endpoints to monitor.
    :param discovery:
        The treadmill.discovery object/iterator. Loop over discovery never
        ends, and it yields results in a form:
        appname:endpoint hostname:port
        appname:endpoint

        Absense of hostname:port indicates that given endpoint no longer
        exists.
    """
    _LOGGER.info('Starting vring: %r %r %r', ring, routing, endpoints)
    vring_state = {}
    iptables.configure_dnat_rules(set(), chain=ring)
    for (app, hostport) in discovery.iteritems():
        # app is in the form appname:endpoint. We care only about endpoint
        # name.
        name_unused, proto, endpoint = app.split(':')
        # Ignore if endpoint is not in routing (only interested in endpoints
        # that are in routing table).
        if endpoint not in endpoints:
            continue

        private_port = routing[endpoint]
        if hostport:
            host, public_port = hostport.split(':')
            ipaddr = socket.gethostbyname(host)
            vring_route = firewall.DNATRule(proto=proto,
                                            orig_ip=ipaddr,
                                            orig_port=private_port,
                                            new_ip=ipaddr,
                                            new_port=public_port)
            _LOGGER.info('add vring route: %r', vring_route)
            vring_state[app] = vring_route
            iptables.add_dnat_rule(vring_route, chain=ring)
        else:
            vring_route = vring_state.get(app, None)
            if vring_route:
                _LOGGER.info('del vring route: %r', vring_route)
                iptables.delete_dnat_rule(vring_route, chain=ring)
