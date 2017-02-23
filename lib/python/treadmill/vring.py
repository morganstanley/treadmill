"""Manage a port-redirect ring between Treadmill containers.

Each vring manages chain of iptables output rules, which enables applications
that expect to find their peers on a "well-defined" constant port to be
deployed inside the container.
"""
from __future__ import absolute_import

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


def run(ring, routing, endpoints, discovery, skip=None):
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
    :param skip:
        set of hosts to skip when creating iptable rules.
    """
    _LOGGER.info('Starting vring: %r %r %r %r',
                 ring, routing, endpoints, skip)
    vring_state = {}
    iptables.configure_nat_rules(set(), chain=ring)
    for (app, hostport) in discovery.iteritems():
        # app is in the form appname:endpoint. We care only about endpoint
        # name.
        _name, proto, endpoint = app.split(':')
        # Ignore if endpoint is not in routing (only interested in endpoints
        # that are in routing table).
        if endpoint not in endpoints:
            continue

        private_port = int(routing[endpoint])
        if hostport:
            host, public_port = hostport.split(':')
            if skip and host in skip:
                _LOGGER.info('Skipping: %s', hostport)
                continue

            ipaddr = socket.gethostbyname(host)
            public_port = int(public_port)
            vring_route = (proto, ipaddr, public_port)
            _LOGGER.info('add vring route: %r', vring_route)
            vring_state[app] = vring_route
            dnat_rule = firewall.DNATRule(
                proto=proto,
                orig_ip=ipaddr,
                orig_port=private_port,
                new_ip=ipaddr,
                new_port=public_port
            )
            snat_rule = firewall.SNATRule(
                proto=proto,
                orig_ip=ipaddr,
                orig_port=public_port,
                new_ip=ipaddr,
                new_port=private_port
            )
            iptables.add_dnat_rule(dnat_rule, chain=ring)
            iptables.add_snat_rule(snat_rule, chain=ring)

        else:
            vring_route = vring_state.pop(app, None)
            if not vring_route:
                continue

            _LOGGER.info('del vring route: %r', vring_route)
            proto, ipaddr, public_port = vring_route
            dnat_rule = firewall.DNATRule(
                proto=proto,
                orig_ip=ipaddr,
                orig_port=private_port,
                new_ip=ipaddr,
                new_port=public_port
            )
            snat_rule = firewall.SNATRule(
                proto=proto,
                orig_ip=ipaddr,
                orig_port=public_port,
                new_ip=ipaddr,
                new_port=private_port,
            )
            iptables.delete_dnat_rule(dnat_rule, chain=ring)
            iptables.delete_snat_rule(snat_rule, chain=ring)
