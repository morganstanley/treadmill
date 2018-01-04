"""TAIDW data dumps access.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import csv
import io
import logging
import re

import six

_LOGGER = logging.getLogger(__name__)

# TODO: this is only place core depends on /v. we should move these
#                files to afs.

#: Location of the TAI server dump
SERVER_DAT = ('/v/region/na/appl/cloud/treadmill/data/development/prodperim'
              '/Server.1302.prod.dat')

#: Location of the TAI service dump
SERVICE_DAT = ('/v/region/na/appl/cloud/treadmill/data/development/prodperim'
               '/Cluster_Service.1303.prod.dat')

VIPS_TXT = {
    'prod': '/v/region/na/appl/cloud/treadmill/data/development/prodperim'
            '/tm3-vips-prod.txt'
}

# NOTE(boysson): We need this to make sure that what TAIDW is giving us is a
#                valid IP.
_LOOKS_LIKE_IP_RE = re.compile(r'^(:?[0-9]{1,3}\.){3}[0-9]{1,3}$')


def dump_entry_gen(filename):
    """Generator that yield entries from TAI generated dumps

    :param filename:
        Filename of the data source
    :type filename:
        `str`
    """
    if six.PY2:
        with io.open(filename, 'rb') as dump:
            for entry in csv.DictReader(dump, delimiter=b'\x1c'):
                yield entry
    else:
        with io.open(filename, 'r', newline='') as dump:
            for entry in csv.DictReader(dump, delimiter='\x1c'):
                yield entry


def env_entry_gen(source, env='prod'):
    """Yield only entries of the given environment (defaults to PROD).

    NOTE: This fallback to ESP info when TAM data is not available.
    """
    for entry in source:
        if _is_tam_env(entry, env) or _is_esp_env(entry, env):
            yield entry


def server_ip_gen(source):
    """Consume a Server TAI dump and yield all non-management IPs on PROD
    servers."""

    for entry in source:
        for ip in entry['IP_List'].split(','):
            # filter out management addresses in 192.168/16
            ip = ip.strip()
            if not _LOOKS_LIKE_IP_RE.match(ip):
                _LOGGER.warning('Ignoring strange IP %r from %r',
                                ip, entry['CI_Name'])
                continue
            if ip.startswith('192.168.'):
                # Skip management IP
                continue
            yield ip


def service_ip_gen(source):
    """Consume a Service TAI dump and yield all service IPs.
    """
    for entry in source:
        ip = entry['IP_Address']
        ip = ip.strip()
        if not _LOOKS_LIKE_IP_RE.match(ip):
            _LOGGER.warning('Ignoring strange IP %r from %r',
                            ip, entry['CI_Name'])
            continue
        yield ip


def vip_ip_gen(filename):
    """Generate list of VIP ips."""
    with io.open(filename) as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith('#'):
                continue
            name, ip = line.split(':')
            ip = ip.strip()

            _LOGGER.debug('Added explicit vip ip: %s: %s', name, ip)
            yield ip


def _is_tam_env(entry, env):
    """Check TAM attributes in TAIDW dump entry to assert if the resource is
    PROD or not.
    """
    return (('Standard_Environment' in entry) and
            (entry['Standard_Environment'] == env))


def _is_esp_env(entry, env):
    """Check ESP attributes in TAIDW dump entry to assert if the resource is
    PROD or not.

    NOTE: We only consider ESP attributes when TAM attributes are undefined
    """
    # NOTE(boysson): ESP can only assert PROD / NONPROD status, no other TAM
    #                environments.
    if env != 'prod':
        return False

    return ((('Standard_Environment' not in entry) or
             (entry['Standard_Environment'] == '')) and
            (('Is_Prod' in entry) and
             (entry['Is_Prod'] == 'Yes')))
