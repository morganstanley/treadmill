"""Implementation of treadmill admin ldap CLI partition plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click
from ldap3.core import exceptions as ldap_exceptions

import six

from treadmill import admin
from treadmill import cli
from treadmill import context


_LOGGER = logging.getLogger(__name__)

_MINIMUM_THRESHOLD = 5


def _resolve_partition_threshold(cell, partition, value):
    """Resolve threshold % to an integer."""
    admin_srv = admin.Server(context.GLOBAL.ldap.conn)
    servers = admin_srv.list({'cell': cell})

    total = 0
    for srv in servers:
        if srv['partition'] == partition:
            total = total + 1

    limit = int((value / 100.0) * total)

    _LOGGER.debug('Total/limit: %s/%s', total, limit)
    return max(limit, _MINIMUM_THRESHOLD)


def init():
    """Configures Partition CLI group"""
    formatter = cli.make_formatter('partition')

    @click.group()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  is_eager=True, callback=cli.handle_context_opt,
                  expose_value=False)
    def partition():
        """Manage partitions"""
        pass

    @partition.command()
    @click.option('-m', '--memory', help='Memory.',
                  callback=cli.validate_memory)
    @click.option('-c', '--cpu', help='CPU.',
                  callback=cli.validate_cpu)
    @click.option('-d', '--disk', help='Disk.',
                  callback=cli.validate_disk)
    @click.option('-s', '--systems', help='System eon id list', type=cli.LIST)
    @click.option('-t', '--down-threshold', help='Down threshold.')
    @click.option('-r', '--reboot-schedule', help='Reboot schedule.',
                  callback=cli.validate_reboot_schedule)
    @click.argument('partition')
    @cli.admin.ON_EXCEPTIONS
    def configure(memory, cpu, disk, systems,
                  down_threshold, reboot_schedule, partition):
        """Create, get or modify partition configuration"""
        # Disable too many branches.
        #
        # pylint: disable=R0912
        cell = context.GLOBAL.cell
        admin_part = admin.Partition(context.GLOBAL.ldap.conn)

        attrs = {}
        if memory:
            attrs['memory'] = memory
        if cpu:
            attrs['cpu'] = cpu
        if disk:
            attrs['disk'] = disk
        if systems:
            if systems == ['-']:
                attrs['systems'] = None
            else:
                attrs['systems'] = list(six.moves.map(int, systems))
        if down_threshold:
            if down_threshold.endswith('%'):
                attrs['down-threshold'] = _resolve_partition_threshold(
                    cell, partition, int(down_threshold[:-1])
                )
            else:
                attrs['down-threshold'] = int(down_threshold)
        if reboot_schedule:
            attrs['reboot-schedule'] = reboot_schedule

        if attrs:
            try:
                admin_part.create([partition, cell], attrs)
            except ldap_exceptions.LDAPEntryAlreadyExistsResult:
                admin_part.update([partition, cell], attrs)

        try:
            cli.out(formatter(admin_part.get([partition, cell])))
        except ldap_exceptions.LDAPNoSuchObjectResult:
            click.echo('Partition does not exist: %s' % partition, err=True)

    @partition.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List partitions"""
        cell = context.GLOBAL.cell
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        partitions = admin_cell.partitions(cell)

        cli.out(formatter(partitions))

    @partition.command()
    @click.argument('label')
    @cli.admin.ON_EXCEPTIONS
    def delete(label):
        """Delete a partition"""
        cell = context.GLOBAL.cell
        admin_part = admin.Partition(context.GLOBAL.ldap.conn)

        try:
            admin_part.delete([label, cell])
        except ldap_exceptions.LDAPNoSuchObjectResult:
            click.echo('Partition does not exist: %s' % label, err=True)

    del configure
    del _list
    del delete

    return partition
