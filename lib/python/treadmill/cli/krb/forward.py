"""Forward Kerberos tickets to the cell ticket locker.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import socket
import sys

import click

from treadmill import cli
from treadmill import context
from treadmill import dnsutils
from treadmill import exc
from treadmill import restclient
from treadmill import tickets

_LOGGER = logging.getLogger(__name__)

_ON_EXCEPTIONS = cli.handle_exceptions([
    (exc.InvalidInputError, None),
])


def _forward_ticket(cells):
    """Forward tickets to list of cells."""
    dns_domain = context.GLOBAL.dns_domain

    tktfwd_spn = None
    if os.name == 'nt':
        _LOGGER.fatal('Unsupported platform.')
        return 100

    rc = 0
    for cellname in cells:
        endpoints = _check_cell(cellname, 'ticketsreceiver', dns_domain)
        if not endpoints:
            _LOGGER.warning('All ticket receiver endpoints are down, cell: %s',
                            cellname)
            rc = 2

        for host, port in endpoints:
            if tickets.forward(host, int(port)):
                _LOGGER.info('Tickets forwarded successfully: %s %s:%s',
                             cellname, host, port)
            else:
                _LOGGER.warning('Error forwarding tickets: %s %s:%s',
                                cellname, host, port)
                rc = 1

    return rc


def _get_cells():
    """Get all cell names"""
    restapi = context.GLOBAL.admin_api()
    cells = restclient.get(restapi, '/cell/').json()

    return [cell['_id'] for cell in cells]


def _check_cell(cellname, appname, dns_domain):
    """Return active endpoint for the locker given cell name."""
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

    active.sort()
    return active


def init():
    """Return top level command handler"""

    @click.command()
    @click.option('--cell', help='List of cells',
                  type=cli.LIST)
    @_ON_EXCEPTIONS
    def forward(cell):
        """Forward Kerberos tickets to the cell ticket locker."""
        _LOGGER.setLevel(logging.INFO)
        cells = cell
        if not cell:
            cells = _get_cells()

        rc = _forward_ticket(cells)
        sys.exit(rc)

    return forward
