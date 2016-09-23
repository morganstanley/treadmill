"""Treadmill DNS cli"""
from __future__ import absolute_import

import logging
import socket
import dns.resolver  # pylint: disable=E0611
import dns.rdatatype  # pylint: disable=E0611

import click

from treadmill import admin
from treadmill import cli
from treadmill import context
from treadmill import dnsutils


_LOGGER = logging.getLogger(__name__)


def init():
    """Treadmill DNS CLI"""

    @click.group(name='dns')
    @click.option('--ldap', required=True, envvar='TREADMILL_LDAP')
    @click.option('--ldap-search-base', required=True,
                  envvar='TREADMILL_LDAP_SEARCH_BASE')
    def dns_group(ldap, ldap_search_base):
        """Treadmill DNS CLI"""
        cli.init_logger('admin.yml')
        context.GLOBAL.ldap.url = ldap
        context.GLOBAL.ldap.search_base = ldap_search_base

    @dns_group.command()
    def ok():  # pylint: disable=C0103
        """Test whether the configured CitDNS servers are up and running"""
        admin_dns = admin.DNS(context.GLOBAL.ldap.conn)
        dns_servers = admin_dns.list({})
        _LOGGER.debug('dns_servers: %r', dns_servers)

        for dns_server in dns_servers:
            verify_dns(dns_server['_id'], dns_server['server'],
                       dns_server['port'], dns_server['fqdn'])

    del ok

    return dns_group


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
