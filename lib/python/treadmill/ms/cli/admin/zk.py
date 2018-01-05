"""Zookeeper status interface.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click
from ldap3.core import exceptions as ldap_exceptions

from treadmill import admin
from treadmill import cli
from treadmill import context
from treadmill import utils
from treadmill import zkadmin

_LOGGER = logging.getLogger(__name__)


def zk_group(top):
    """Check Zookeeper status."""

    on_exceptions = cli.handle_exceptions([
        (context.ContextError, None),
        (ldap_exceptions.LDAPNoSuchObjectResult, 'Error: invalid cell.'),
    ])

    @top.command()
    @on_exceptions
    # Disable C0103: Invalid name
    def ok():  # pylint: disable=C0103
        """Check Zookeeper state (ruok)."""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        cell = admin_cell.get(context.GLOBAL.cell)
        for master in cell['masters']:
            hostname = master['hostname']
            port = master['zk-client-port']
            try:
                zk_status = zkadmin.netcat(hostname, port, 'ruok\n')
                print('%s:%s' % (hostname, port), zk_status)
            except Exception as err:  # pylint: disable=W0703
                print(str(err))

    @top.command()
    @on_exceptions
    def stat():
        """Get Zookeeper stats (stat)."""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        cell = admin_cell.get(context.GLOBAL.cell)
        for master in cell['masters']:
            hostname = master['hostname']
            port = master['zk-client-port']
            zk_status = zkadmin.netcat(hostname, port, 'stat\n')
            print('%s:%s' % (hostname, port), zk_status)

    @top.command()
    @on_exceptions
    def environ():
        """Outputs eval friendly environment vars for given cell."""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        cell = admin_cell.get(context.GLOBAL.cell)
        zk_hostports = ','.join([
            '%s:%s' % (master['hostname'], master['zk-client-port'])
            for master in cell['masters']
        ])
        url = 'zookeeper://%s@%s/treadmill/%s' % (
            cell['username'],
            zk_hostports,
            context.GLOBAL.cell
        )

        print('export TREADMILL_CELL=%s' % context.GLOBAL.cell)
        print('export TREADMILL_ZOOKEEPER=%s' % url)
        print('export TREADMILL_ZOOKEEPER_HOSTS=%s' % zk_hostports)
        print('export TREADMILL_ZOOKEEPER_PROID=%s' % cell['username'])

    @top.command()
    @on_exceptions
    def shell():
        """Starts Zookeeper shell."""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        cell = admin_cell.get(context.GLOBAL.cell)
        zk_hostports = [
            '%s:%s' % (master['hostname'], master['zk-client-port'])
            for master in cell['masters']
        ]

        args = [
            '/ms/dist/sam/PROJ/zookeeper/1.12.0/bin/zkKerbCli.sh',
            '-prodid', cell['username'],
            '-conn', ','.join(zk_hostports),
        ]
        _LOGGER.debug('command: %s', ' '.join(args))
        utils.sane_execvp(args[0], args)

    del shell
    del environ
    del ok
    del stat


def init():
    """Return top level command handler."""
    # Redefining ldap
    # pylint: disable=W0621

    @click.group()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    def top():
        """Check status of Zookeeper ensemble."""
        pass

    zk_group(top)
    return top
