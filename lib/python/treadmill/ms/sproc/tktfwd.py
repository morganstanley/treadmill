"""Forward tickets to the cell ticket locker.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import logging
import os
import pwd
import socket
import time
import collections

import click
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import admin
from treadmill import context
from treadmill import dnsutils
from treadmill import subproc


_LOGGER = logging.getLogger(__name__)

_REALM = 'is1.morgan'


def _send_tkt_v2(endpoints, tkt_file):
    """Forwards tickets to the ticket locker."""
    cmd_environ = dict(os.environ.items())
    cmd_environ['KRB5CCNAME'] = 'FILE:%s' % tkt_file

    for hostport in endpoints:
        host, port = hostport

        args = [
            'tkt_send_v2',
            '-h{}'.format(host),
            '-p{}'.format(port),
        ]

        try:
            subproc.check_call(args, environ=cmd_environ)
            _LOGGER.info('Successfully forwarded tickets: %s, %r',
                         tkt_file, endpoints)
        except subprocess.CalledProcessError:
            _LOGGER.exception('Failed to forward tickets: %r', args)


def _send_tkt_v1(realm, endpoints, tkt_file):
    """Forwards ticket to the ticket locker - legacy protocol."""
    args = [
        'tkt_send',
        '--realm=%s' % realm,
        '--princ=host',
        '--timeout=5',
        '--endpoints=%s' % ','.join(['%s:%s' % (host, port)
                                     for host, port in endpoints])
    ]

    cmd_environ = dict(os.environ.items())
    cmd_environ['KRB5CCNAME'] = 'FILE:%s' % tkt_file

    try:
        subproc.check_call(args, environ=cmd_environ)
        _LOGGER.info('Successfully forwarded tickets: %s, %r',
                     tkt_file, endpoints)
    except subprocess.CalledProcessError:
        _LOGGER.exception('Failed to forward tickets: %r', args)


def _check_cell(cellname, appname, dns_domain):
    """Check that locker service is defined and up for given cell."""
    srvrec = '_tickets._tcp.{}.{}.cell.{}'.format(appname,
                                                  cellname,
                                                  dns_domain)
    result = dnsutils.srv(srvrec, context.GLOBAL.dns_server)

    active = []
    for host, port, _, _ in result:
        sock = None
        try:
            sock = socket.create_connection((host, port), 1)
            active.append((host, port))
        except socket.error:
            _LOGGER.warning('Ticket endpoint [%s] is down: %s:%s',
                            cellname, host, port)
        finally:
            if sock:
                sock.close()

    return active


def _tktfwd_loop(realm):
    """Continuously send tickets."""
    admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
    dns_domain = context.GLOBAL.dns_domain

    if os.geteuid() == 0:
        glob_pattern = '/var/spool/tickets/*'
    else:
        glob_pattern = '/var/spool/tickets/%s' % pwd.getpwuid(os.geteuid())[0]

    _LOGGER.info('Using glob pattern: %s', glob_pattern)

    while True:
        rc = subproc.call(['ticket', '-v'])
        _LOGGER.info('Tickets refreshed, ticket: rc = %s', rc)

        cellnames = [cell['_id'] for cell in admin_cell.list({})]
        ticket_endpoints = collections.defaultdict(dict)

        for cellname in cellnames:
            # Check new protocol first, fallback to old if endpoints not
            # found.
            ticket_endpoints[cellname]['v2'] = _check_cell(cellname,
                                                           'tickets-v2',
                                                           dns_domain)
            ticket_endpoints[cellname]['v1'] = _check_cell(cellname,
                                                           'tickets',
                                                           dns_domain)

        for tkt_file in glob.glob(glob_pattern):
            for cell, endpoints in six.iteritems(ticket_endpoints):
                if endpoints['v2']:
                    _LOGGER.info('Using v2 protocol: %s - %s', cell, endpoints)
                    _send_tkt_v2(endpoints['v2'], tkt_file)
                elif endpoints['v1']:
                    _LOGGER.info('Using v1 protocol: %s - %s', cell, endpoints)
                    _send_tkt_v1(realm, endpoints['v1'], tkt_file)
                else:
                    _LOGGER.warning(
                        'No active ticket endpoints for cell: %s',
                        cell
                    )

        time.sleep(60 * 60)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--realm', help='Treadmill locker realm', default=_REALM)
    @click.option(
        '--aliases-path', required=False,
        default='node:node.ms',
        envvar='TREADMILL_ALIASES_PATH',
        help='Colon separated command alias paths'
    )
    def tktfwd(realm, aliases_path):
        """Continuously forward prestashed tickets to the ticket locker."""
        if aliases_path:
            os.environ['TREADMILL_ALIASES_PATH'] = aliases_path
        _tktfwd_loop(realm)

    return tktfwd
