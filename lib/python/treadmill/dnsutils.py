"""DNS resolution methods.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

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


def _build_result_set(answer, ignore_additional):
    """Return a list of SRV instances for a DNS answer.
    :rtype: list of srvlookup.SRV
    """
    if not answer:
        return []

    if ignore_additional:
        resource_map = {}
    else:
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


def make_resolver(dns_server=None):
    """Returns DNS resolver."""
    resolver = dns.resolver.Resolver()

    # handle dns host and port override
    if dns_server:
        if dns_server[0] and all(dns_server[0]):
            resolver.nameservers = [socket.gethostbyname(host)
                                    for host in dns_server[0]]
        if dns_server[1]:
            resolver.port = dns_server[1]

    return resolver


# Code from dyndns/resolve.py
# TODO: remove once dyndns project is opensourced
def query(name, rdatatype, dns_server=None):
    """Send query to supplied DNS resolver

    :return: None if no results could be found
    """
    resolver = make_resolver(dns_server)

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
def a(label, dns_server=None):
    """Resolve an A resource record

    :param label: label to lookup
    :type zone: str

    :param dns_server: dns host and port information
    :type dns_server: (list, int)

    :return: list of IPs
    """
    return [str(rec) for rec in query(label, dns.rdatatype.A, dns_server)]


def cname(label, dns_server=None):
    """Resolve a CNAME resource record

    :param label: label to lookup
    :type zone: str

    :param dns_server: dns host and port information
    :type dns_server: (list, int)

    :return: a list of cnames
    """
    return [str(rec) for rec in query(label, dns.rdatatype.CNAME, dns_server)]


def srv(label, dns_server=None, ignore_additional=True):
    """Resolve a CNAME resource record

    :param label: label to lookup
    :type zone: str

    :param dns_server: dns host and port information
    :type dns_server: (list, int)

    :return: a list of tuples (ip, port, prio, weight)
    """
    return _build_result_set(query(label, dns.rdatatype.SRV, dns_server),
                             ignore_additional)


def txt(label, dns_server=None):
    """Resolve a TXT resource record

    :param label: label to lookup
    :type zone: str

    :param dns_server: dns host and port information
    :type dns_server: (list, int)

    :return: list txt record
    """
    return [str(rec).strip('"')
            for rec in query(label, dns.rdatatype.TXT, dns_server)]


def soa(label, dns_server=None):
    """Resolve a SOA resource record

    :param label: label to lookup
    :type zone: str

    :param dns_server: dns host and port information
    :type dns_server: (list, int)

    :return: a list of soa records
    """
    return query(label, dns.rdatatype.SOA, dns_server)


def ns(fqdn, dns_server=None):
    """Resolve DNS zone.
    """
    return [str(rec) for rec in query(fqdn, dns.rdatatype.NS, dns_server)]


def srv_target_to_dict(srv_rec):
    """Convert SRV record tuple to dict.
    """
    host, port, prio, weight = srv_rec
    return {'host': host,
            'port': port,
            'priority': prio,
            'weight': weight}


def srv_rec_to_url(srv_rec, srv_name=None, protocol=None):
    """Convert SRV record to URL.
    """
    if not protocol:
        if srv_name:
            protocol, _rest = srv_name.split('.', 1)
            protocol = protocol[1:]
        else:
            protocol = ''

    tgt = srv_target_to_dict(srv_rec)
    return '%s://%s:%s' % (protocol,
                           tgt['host'],
                           tgt['port'])
