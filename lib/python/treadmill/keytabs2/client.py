"""
Handles keytab forwarding from keytab locker to the node. This is a upgraded
version from `treadmill.keytab` which supports requesting by SPNs and relevant
ownership.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import contextlib
import logging
import os
import random
import socket

from treadmill import context
from treadmill import dnsutils
from treadmill import discovery
from treadmill import fs
from treadmill import keytabs2
from treadmill.gssapiprotocol import jsonclient

_LOGGER = logging.getLogger(__name__)


@contextlib.contextmanager
def connect_endpoint(host, port):
    """open keytab2 connection
    """
    service = 'host@%s' % host
    _LOGGER.info('connecting: %s:%s, %s', host, port, service)
    client = jsonclient.GSSAPIJsonClient(host, int(port), service)

    if not client.connect():
        error = 'Cannot connect to {}:{}'.format(host, port)
        _LOGGER.error(error)
        raise keytabs2.KeytabClientError(error)

    _LOGGER.debug('connected to: %s:%s, %s', host, port, service)
    try:
        yield client
    finally:
        client.disconnect()


def send_request(client, request):
    """send keytab2 request to endpoint
    """
    res = {}
    client.write_json(request)
    res = client.read_json()
    if '_error' in res:
        _LOGGER.warning('keytab locker internal err: %s', res['_error'])
        raise keytabs2.KeytabClientError(res['_error'])

    if not res['success']:
        _LOGGER.warning('get keytab err: %s', res['message'])
        raise keytabs2.KeytabClientError(res['message'])

    return res


def del_keytab(client, keytabs):
    """delete keytab to keytab locker

    keytabs are keytabs files list
    """
    request = {
        'action': 'del',
        'keytabs': [keytabs2.read_keytab(kt) for kt in keytabs]
    }
    return send_request(client, request)


def put_keytab(client, keytabs):
    """put keytab to keytab locker

    keytabs are keytabs files list
    """
    request = {
        'action': 'put',
        'keytabs': [keytabs2.read_keytab(kt) for kt in keytabs]
    }
    return send_request(client, request)


def get_keytabs(client, app_name):
    """get keytabs from keytab locker
    """
    request = {
        'action': 'get',
        'app': app_name,
    }
    return send_request(client, request)


def dump_keytabs(client, app_name, dest):
    """Get VIP keytabs from keytab locker server.
    """
    res = get_keytabs(client, app_name)

    for ktname, encoded in res['keytabs'].items():
        if not encoded:
            _LOGGER.warning('got empty keytab %s', ktname)
            continue

        _LOGGER.info('got keytab %s:%r',
                     ktname, encoded)
        kt_file = os.path.join(dest, ktname)
        keytabs2.write_keytab(kt_file, encoded)


def request_keytabs(zkclient, app_name, spool_dir, pattern):
    """Request VIP keytabs from the keytab locker.

    :param zkclient: Existing zk connection.
    :param app_name: Appname of container
    :param spool_dir: Path to keep keytabs fetched from keytab locker.
    :param pattern: app pattern for discovery endpoint of locker
    """
    iterator = discovery.iterator(zkclient, pattern, 'keytabs', False)
    hostports = []

    for (_app, hostport) in iterator:
        if not hostport:
            continue
        host, port = hostport.split(':')
        hostports.append((host, int(port)))

    random.shuffle(hostports)

    for (host, port) in hostports:
        fs.mkdir_safe(spool_dir)
        try:
            with connect_endpoint(host, port) as client:
                dump_keytabs(client, app_name, spool_dir)
            return
        # pylint: disable=broad-except
        except Exception as err:
            _LOGGER.warning(
                'Failed to get keytab from %s:%d: %r', host, port, err
            )

    # if no host, port can provide keytab
    raise keytabs2.KeytabClientError(
        'Failed to get keytabs from {}'.format(hostports)
    )


def _check_cell(cellname, srvrec):
    """Check that locker service is defined and up for given cell."""
    result = dnsutils.srv(srvrec, context.GLOBAL.dns_server)
    active = []
    for host, port, _, _ in result:
        sock = None
        try:
            sock = socket.create_connection((host, port), 1)
            active.append((host, port))
        except socket.error:
            _LOGGER.warning('Keytab endpoint [%s] is down: %s:%s',
                            cellname, host, port)
        finally:
            if sock:
                sock.close()

    return active


def get_endpoints(srv_pattern):
    """Get all endpoints of keytab locker
    """
    admin_cell = context.GLOBAL.admin.cell()
    domain = context.GLOBAL.dns_domain

    cellnames = [cell['_id'] for cell in admin_cell.list({})]
    keytab_endpoints = collections.defaultdict(list)

    for cellname in cellnames:
        # Check new protocol first, fallback to old if endpoints not
        # found.
        srvrec = srv_pattern.format(CELL=cellname, DOMAIN=domain)
        keytab_endpoints[cellname] = _check_cell(cellname, srvrec)

    return keytab_endpoints
