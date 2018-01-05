"""Treadmill DNS publish

This is the main driver module for publishing and setting up the critical
Treadmill DNS zones and resource records. This module will do the following:

    1. Create necessary zones, i.e.
        a. $fqdn
        b. $cell.cell.$fqdn
        c. $region.region.$fqdn
        d. $campus.campus.$fqdn
    2. Create LDAP SRV records
    3. Create Zookeeper TXT records
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import socket
import dns.resolver
import dns.rdatatype

import click
import six

from treadmill import admin
from treadmill import cli
from treadmill import context
from treadmill import dnsutils
from treadmill import zkutils

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import dyndnsclient

_LOGGER = logging.getLogger(__name__)


def _zone_exists(dns_host, dns_port, fqdn):
    """Check if zone exists on DNS server."""
    answer = dnsutils.ns(fqdn, ([dns_host], dns_port))
    _LOGGER.info('Zone %s exists: %s', fqdn, bool(answer))
    return bool(answer)


def _publish_zone(rest_srv, nameful_master, fqdn, nameservers):
    """Create FQDN zone, if missing"""
    _LOGGER.info('Creating zone @%s: %s, %r', rest_srv, fqdn, nameservers)

    host, _port = rest_srv.split(':')
    dyndns_client = dyndnsclient.DyndnsClient([rest_srv])

    rest_host_ip = socket.gethostbyname(host)
    # If master is set, then this is a slave DNS instance
    master = nameful_master if rest_host_ip != nameful_master else None

    dyndns_client.post('bind/zone/' + fqdn, nameservers=nameservers,
                       master=master)


def _publish_ldap(dyndns_client, fqdn, cell, ldapurl):
    """Create LDAP record for given cell."""
    ldaphost, ldapport = ldapurl[len('ldap://'):].split(':')
    _LOGGER.info('Creating: _ldap._tcp.%s.%s: %s:%s',
                 cell, fqdn, ldaphost, ldapport)
    dyndns_client.delete('srv/%s/_ldap._tcp.%s' % (fqdn, cell))
    dyndns_client.post('srv/%s/_ldap._tcp.%s' % (fqdn, cell),
                       target=ldaphost, port=ldapport)


def _publish_zkurl(dyndns_client, fqdn, cell, zkurl):
    """Create TXT record with ZK connection string."""
    label = 'zk.{0}.{1}.'.format(cell, fqdn)
    _LOGGER.info('Creating TXT record: %s => %s', label, zkurl)

    endpoint = 'txt/{0}/{1}'.format(fqdn, label)

    dyndns_client.delete(endpoint)
    dyndns_client.post(endpoint, txt=zkurl)


def _cell_zkurl(cell_obj):
    """Constructs ZK connection string from cell object."""
    hostports = [master['hostname'] + ':' + str(master['zk-client-port'])
                 for master in cell_obj['masters']]
    username = cell_obj['username']
    cellname = cell_obj['_id']
    _LOGGER.debug('hostports: %r, username: %s, cellname: %s',
                  hostports, username, cellname)

    return 'zookeeper://{0}@{1}/treadmill/{2}'.format(
        username, ','.join(hostports), cellname
    )


def _primary_dyndns(zkurl):
    """Get the primary DynDNS server and port"""
    zkclient = zkutils.connect(zkurl)
    data = zkutils.get(zkclient, '/nameful', strict=False)
    _LOGGER.debug('data: %r', data)
    return data


def _rest_srv_port(rest_srvs, dns_srv):
    """Get the corresponding REST server for the provided DNS server

    This function assumes a 1:1 match of DNS + REST
    """
    for rest_srv in rest_srvs:
        if rest_srv.startswith(dns_srv):
            return rest_srv

    return None


def verify_dns(name, host, port, fqdn):
    """Verify DNS is running and then the main FQDN zone"""
    _LOGGER.info('Verifying: %s', name)
    try:
        socket.create_connection((host, port), 5)
        _LOGGER.info('DNS server %s:%s ok.', host, port)

        resolver = dns.resolver.Resolver()
        resolver.nameservers = [socket.gethostbyname(host)]
        resolver.port = port

        verify_zone(fqdn, resolver)

    except socket.error:
        _LOGGER.error('DNS server %s:%s down.', host, port)


def verify_zone(fqdn, resolver):
    """Verify zone"""
    try:
        zones = dnsutils.ns(fqdn, resolver)
        if zones:
            _LOGGER.info('Zone %s ok', fqdn)
        else:
            _LOGGER.error('Zone %s not ok.', fqdn)
    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Unhandled exception.')


def init():
    """Initiliaze this plugin"""

    @click.group()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  is_eager=True, callback=cli.handle_context_opt,
                  expose_value=False)
    def dns():  # pylint: disable=W0621
        """Manage DNS Resource Records"""
        pass

    @dns.command()
    def ok():  # pylint: disable=C0103
        """Test whether the configured CitDNS servers are up and running"""
        admin_dns = admin.DNS(context.GLOBAL.ldap.conn)
        dns_servers = admin_dns.list({})
        _LOGGER.debug('dns_servers: %r', dns_servers)

        for dns_server in dns_servers:
            for server_port in dns_server['server']:
                server, port = server_port.split(':')
                verify_dns(dns_server['_id'], server, int(port),
                           dns_server['fqdn'])

    @dns.command()
    @click.option('--scopes', help='List of cell DNS scopes.', type=cli.DICT)
    @click.argument('name', nargs=1, required=True)
    @cli.admin.ON_EXCEPTIONS
    def zones(scopes, name):
        """Verify or create DNS zones"""
        cell = context.GLOBAL.cell
        admin_dns = admin.DNS(context.GLOBAL.ldap.conn)
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)

        dns_obj = admin_dns.get(name)
        _LOGGER.debug('dns_obj: %r', dns_obj)

        cell_obj = admin_cell.get(cell)
        _LOGGER.debug('cell_obj: %r', cell_obj)

        fqdn = context.GLOBAL.dns_domain or dns_obj['fqdn']
        nameful = _primary_dyndns(dns_obj['zkurl'])

        # Default zones
        zones = [fqdn,
                 '.'.join([cell, 'cell', fqdn])]

        nameservers = dns_obj['nameservers']

        for server_port in dns_obj['server']:
            dns_srv, dns_port = server_port.split(':')
            _LOGGER.debug('dns_srv: %s, dns_port: %s', dns_srv, dns_port)

            # scopea is dict like:
            #
            # region: na
            # campus: ny
            #
            # It will create zone:
            #
            # <campus>.campus.<tm-fqdn>
            # <region>.region.<tm-fqdn>
            for scope_name, scope in six.iteritems(scopes or {}):
                zones.append('.'.join([scope, scope_name, fqdn]))

            for zone in zones:
                _LOGGER.info('Configure zone: %s', zone)
                if not _zone_exists(dns_srv, int(dns_port), zone):
                    rest_srv = _rest_srv_port(dns_obj['rest-server'], dns_srv)
                    _publish_zone(rest_srv, nameful['ip'], zone, nameservers)

    @dns.command()
    @click.argument('name', nargs=1, required=True)
    @cli.admin.ON_EXCEPTIONS
    def publish(name):
        """Publish critical DNS records"""
        cell = context.GLOBAL.cell
        admin_dns = admin.DNS(context.GLOBAL.ldap.conn)
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)

        dns_obj = admin_dns.get(name)
        _LOGGER.debug('dns_obj: %r', dns_obj)

        cell_obj = admin_cell.get(cell)
        _LOGGER.debug('cell_obj: %r', cell_obj)

        fqdn = context.GLOBAL.dns_domain or dns_obj['fqdn']
        nameful = _primary_dyndns(dns_obj['zkurl'])

        dyndns_servers = ['%s:%s' % (nameful['host'], nameful['port'])]
        dyndns_client = dyndnsclient.DyndnsClient(dyndns_servers)

        # Publish ldap record.
        # TODO: do we need to check if srv record already exists?
        _publish_ldap(dyndns_client, fqdn, cell, context.GLOBAL.ldap.url)
        _publish_zkurl(dyndns_client, fqdn, cell, _cell_zkurl(cell_obj))

    del ok
    del zones
    del publish

    return dns
