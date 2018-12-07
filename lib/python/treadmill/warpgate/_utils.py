"""Warpgate utilities.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import netdev
from treadmill import iptables


_WG_DEV_FORMAT = 'wg.{id:08x}'  # IFNAMSIZ is 16 bytes


def wg_dev_list():
    """List all warpgate devices.
    """
    return [
        devname
        for devname in netdev.dev_list(typefilter=netdev.DevType.GRE)
        if devname.startswith('wg.')
    ]


def wg_dev_create(unique_id, tun_localaddr, tun_remoteaddr,
                  ll_devname, ll_localaddr, ll_remoteaddr):
    """Configure a Warpgate tunnel interface.
    """
    tun_devname = _WG_DEV_FORMAT.format(id=unique_id)
    netdev.gre_create(
        grename=tun_devname,
        devname=ll_devname,
        localaddr=ll_localaddr,
        remoteaddr=ll_remoteaddr,
        key=unique_id,
    )
    netdev.addr_add(
        addr=tun_localaddr,
        devname=tun_devname,
        ptp_addr=tun_remoteaddr,
        addr_scope='host'
    )
    return tun_devname


def wg_dev_delete(devname):
    """Delete a WarpGate tunnel interface.
    """
    netdev.gre_delete(devname)


def wg_route_create(devname, localaddr, remoteaddr, routes):
    """Add a list of routes, via a remote tunnel address, on a give device
    """
    for route in routes:
        netdev.route_add(
            route,
            devname=devname,
            via=remoteaddr,
            src=localaddr,
            route_scope='global'
        )


# TODO: add server side firewall
def wg_firewall_client_init_once():
    """One time initialization of the client side firewall.
    """
    iptables.create_chain('filter', 'WG_INGRESS')
    iptables.add_raw_rule(
        'filter', 'INPUT',
        (
            ' -m state --state ESTABLISHED,RELATED'
            ' -j ACCEPT'
        ),
        safe=True
    )
    iptables.add_raw_rule(
        'filter', 'INPUT',
        (
            ' -m state --state INVALID'
            ' -j DROP'
        ),
        safe=True
    )


def wg_firewall_client_init(devname, endpoints):
    """Client firewall setup for a new device and endpoints.
    """
    iptables.flush_chain('filter', 'WG_INGRESS')
    # This chain only filters on the WarpGate interface
    for endpoint in endpoints:
        assert endpoint['proto'] in ['udp', 'tcp']
        iptables.add_raw_rule(
            'filter', 'WG_INGRESS',
            (
                ' -m state --state NEW'
                ' -p {proto} -m {proto} --dport {port}'
                ' -j ACCEPT'
            ).format(
                proto=endpoint['proto'],
                port=endpoint['port'],
            )
        )
    # Anything not explicitely allowed is denied
    iptables.add_raw_rule(
        'filter', 'WG_INGRESS',
        '-j DROP'
    )
    iptables.add_raw_rule(
        'filter', 'INPUT',
        (
            '-i {devname}'
            ' -j WG_INGRESS'
        ).format(
            devname=devname
        )
    )


def wg_firewall_client_fini(devname):
    """Client firewall cleanup after disconnect.
    """
    iptables.delete_raw_rule(
        'filter', 'INPUT',
        (
            '-i {devname}'
            ' -j WG_INGRESS'
        ).format(
            devname=devname
        )
    )


__all__ = [
    'wg_dev_list',
    'wg_dev_create',
    'wg_route_create',
    'wg_firewall_client_init_once',
    'wg_firewall_client_init',
    'wg_firewall_client_fini',
]
