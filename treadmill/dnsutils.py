"""
DNS resolution methods
"""

import collections
import logging
import socket

import dns.exception
import dns.rdatatype
import dns.resolver

_LOGGER = logging.getLogger(__name__)


# Code of _build_ functions below copied from srvlookup.py

# https://github.com/aweber/srvlookup/blob/master/srvlookup.py
def _build_resource_to_address_map(answer):
    """Return a dictionary that maps resource name to address.
    The response from any DNS query is a list of answer records and
    a list of additional records that may be useful.  In the case of
    SRV queries, the answer section contains SRV records which contain
    the service weighting information and a DNS resource name which
    requires further resolution.  The additional records segment may
    contain A records for the resources.  This function collects them
    into a dictionary that maps resource name to an array of addresses.
    :rtype: dict
    """
    mapping = collections.defaultdict(list)
    for resource in answer.response.additional:
        target = resource.name.to_text()
        mapping[target].extend(record.address
                               for record in resource.items
                               if record.rdtype == dns.rdatatype.A)
    return mapping


def _build_result_set(answer):
    """Return a list of SRV instances for a DNS answer.
    :rtype: list of srvlookup.SRV
    """
    if not answer:
        return []

    resource_map = _build_resource_to_address_map(answer)
    result_set = []
    for resource in answer:
        target = resource.target.to_text()
        if target in resource_map:
            result_set.extend(
                (address, resource.port, resource.priority, resource.weight)
                for address in resource_map[target])
        else:
            result_set.append((target.rstrip('.'), resource.port,
                               resource.priority, resource.weight))
    return result_set


def make_resolver(dns_host, dns_port, nameservers=None):
    """Returns DNS resolver."""
    resolver = dns.resolver.Resolver()
    resolver.port = dns_port
    if nameservers:
        resolver.nameservers = nameservers
    else:
        resolver.nameservers = [socket.gethostbyname(dns_host)]
    return resolver


# Code from dyndns/resolve.py
# TODO: remove once dyndns project is opensourced
def query(name, rdatatype, resolver=None):
    """Send query to supplied DNS resolver

    :return: None if no results could be found
    """
    if not resolver:
        resolver = dns.resolver.Resolver()

    query_str = '%s IN %s' % (name, dns.rdatatype.to_text(rdatatype))
    try:
        return resolver.query(name, rdatatype, tcp=True)
    except dns.exception.Timeout as err:
        _LOGGER.debug('Timeout while querying %s: %s', query_str, err)
    except dns.resolver.NXDOMAIN as err:
        _LOGGER.debug('Query: "%s" does not exist in DNS: %s', query_str, err)
    except dns.resolver.YXDOMAIN:
        # TODO: not sure what "too long" means...
        _LOGGER.debug('Query: "%s" is too long.', query_str)
    except dns.resolver.NoAnswer:
        _LOGGER.debug('Query: "%s" has no answer.', query_str)
    except dns.resolver.NoNameservers:
        _LOGGER.debug('Query "%s" has no name server.', query_str)

    return []


# The following is on purpose to keep inline with other method names
# C0103: Invalid name "aa" for type method (should match
# [a-z_][a-z0-9_]{2,30}$)
# pylint: disable=C0103
def a(label, resolver=None):
    """Resolve an A resource record

    :param label: label to lookup
    :type zone: str

    :param resolver: your own dns.resolver.Resolver
    :type resolver: dns.resolver.Resolver

    :return: list of IPs
    """
    return map(str, query(label, dns.rdatatype.A, resolver))


def cname(label, resolver=None):
    """Resolve a CNAME resource record

    :param label: label to lookup
    :type zone: str

    :param resolver: your own dns.resolver.Resolver
    :type resolver: dns.resolver.Resolver

    :return: a list of cnames
    """
    return map(str, query(label, dns.rdatatype.CNAME, resolver))


def srv(label, resolver=None):
    """Resolve a CNAME resource record

    :param label: label to lookup
    :type zone: str

    :param resolver: your own dns.resolver.Resolver
    :type resolver: dns.resolver.Resolver

    :return: a list of tuples (ip, port, prio, weight)
    """
    return _build_result_set(query(label, dns.rdatatype.SRV, resolver))


def txt(label, resolver=None):
    """Resolve a TXT resource record

    :param label: label to lookup
    :type zone: str

    :param resolver: your own dns.resolver.Resolver
    :type resolver: dns.resolver.Resolver

    :return: list txt record
    """
    return [str(rec).strip('"')
            for rec in query(label, dns.rdatatype.TXT, resolver)]


def ns(fqdn, resolver=None):
    """Resolve DNS zone."""
    return map(str, query(fqdn, dns.rdatatype.NS, resolver))


def srv_target_to_url(srv_rec, srv_target):
    """Convert SRV record to URL"""
    protocol, _rest = srv_rec.split('.', 1)
    host, port, _prio, _weight = srv_target
    return '%s://%s:%s' % (protocol[1:], host, port)
