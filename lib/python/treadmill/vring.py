"""Manage a port-redirect ring between Treadmill containers.

Each vring manages chain of iptables output rules, which enables applications
that expect to find their peers on a "well-defined" constant port to be
deployed inside the container.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import socket

from treadmill import firewall
from treadmill import iptables
from treadmill import sysinfo

_LOGGER = logging.getLogger(__name__)


def run(routing, endpoints, discovery, rulemgr, ip_owner, rules_owner):
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
    :param ``RuleMgr`` rulemgr:
        Firewall rule manager instance.
    :param ``str`` rules_owner:
        Unique name of the container owning all the rules.
    :param ``str`` ip_owner:
        IP of the container owning of the VRing.
    """
    local_host = sysinfo.hostname()
    local_ip = socket.gethostbyname(local_host)

    _LOGGER.info('Starting vring: %r %r %r %r %r',
                 local_host, ip_owner, rules_owner, routing, endpoints)

    # Add reflective rules back to the container
    for endpoint in endpoints:
        dnat_rule = firewall.DNATRule(
            proto=routing[endpoint]['proto'],
            src_ip=ip_owner,
            dst_ip=local_ip,
            dst_port=routing[endpoint]['port'],
            new_ip=ip_owner,
            new_port=routing[endpoint]['port']
        )
        rulemgr.create_rule(chain=iptables.VRING_DNAT,
                            rule=dnat_rule,
                            owner=rules_owner)

    vring_state = {}
    for (app, hostport) in discovery.iteritems():
        # app is in the form appname:endpoint. We care only about endpoint
        # name.
        _name, proto, endpoint = app.split(':')
        # Ignore if endpoint is not in routing (only interested in endpoints
        # that are in routing table).
        if endpoint not in endpoints:
            continue

        private_port = int(routing[endpoint]['port'])
        if hostport:
            host, public_port = hostport.split(':')

            if host == local_host:
                continue

            try:
                ipaddr = socket.gethostbyname(host)
            except socket.gaierror as err:
                _LOGGER.warning('Error resolving %r(%s), skipping.', host, err)
                continue
            public_port = int(public_port)
            vring_route = (proto, ipaddr, public_port)
            _LOGGER.info('add vring route: %r', vring_route)
            vring_state[app] = vring_route
            dnat_rule = firewall.DNATRule(
                proto=proto,
                src_ip=ip_owner,
                dst_ip=ipaddr,
                dst_port=private_port,
                new_ip=ipaddr,
                new_port=public_port
            )
            snat_rule = firewall.SNATRule(
                proto=proto,
                src_ip=ipaddr,
                src_port=public_port,
                dst_ip=ip_owner,
                new_ip=ipaddr,
                new_port=private_port
            )
            rulemgr.create_rule(chain=iptables.VRING_DNAT,
                                rule=dnat_rule,
                                owner=rules_owner)
            rulemgr.create_rule(chain=iptables.VRING_SNAT,
                                rule=snat_rule,
                                owner=rules_owner)

        else:
            vring_route = vring_state.pop(app, None)
            if not vring_route:
                continue

            _LOGGER.info('del vring route: %r', vring_route)
            proto, ipaddr, public_port = vring_route
            dnat_rule = firewall.DNATRule(
                proto=proto,
                src_ip=ip_owner,
                dst_ip=ipaddr,
                dst_port=private_port,
                new_ip=ipaddr,
                new_port=public_port
            )
            snat_rule = firewall.SNATRule(
                proto=proto,
                src_ip=ipaddr,
                src_port=public_port,
                dst_ip=ip_owner,
                new_ip=ipaddr,
                new_port=private_port,
            )
            rulemgr.unlink_rule(chain=iptables.VRING_DNAT,
                                rule=dnat_rule,
                                owner=rules_owner)
            rulemgr.unlink_rule(chain=iptables.VRING_SNAT,
                                rule=snat_rule,
                                owner=rules_owner)
