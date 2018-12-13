"""Implementation of treadmill admin ldap CLI partition plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging

import click

from treadmill.admin import exc as admin_exceptions
from treadmill import cli
from treadmill import context
from treadmill import yamlwrapper as yaml


_LOGGER = logging.getLogger(__name__)

_MINIMUM_THRESHOLD = 5


def _resolve_partition_threshold(cell, partition, value):
    """Resolve threshold % to an integer.
    """
    admin_srv = context.GLOBAL.admin.server()
    servers = admin_srv.list({'cell': cell})

    total = 0
    for srv in servers:
        if srv['partition'] == partition:
            total = total + 1

    limit = int((value / 100.0) * total)

    _LOGGER.debug('Total/limit: %s/%s', total, limit)
    return max(limit, _MINIMUM_THRESHOLD)


def init():
    """Configures Partition CLI group.
    """
    # pylint: disable=too-many-statements

    formatter = cli.make_formatter('partition')

    @click.group()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  is_eager=True, callback=cli.handle_context_opt,
                  expose_value=False)
    def partition():
        """Manage partitions.
        """

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
    @click.option('--data', help='Cell specific data in YAML',
                  type=click.Path(exists=True, readable=True))
    @click.argument('partition')
    @cli.admin.ON_EXCEPTIONS
    def configure(memory, cpu, disk, systems,
                  down_threshold, reboot_schedule, data, partition):
        """Create, get or modify partition configuration.
        """
        # pylint: disable=too-many-branches

        cell = context.GLOBAL.cell
        admin_part = context.GLOBAL.admin.partition()

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
                attrs['systems'] = [int(s) for s in systems]
        if down_threshold:
            if down_threshold.endswith('%'):
                attrs['down-threshold'] = _resolve_partition_threshold(
                    cell, partition, int(down_threshold[:-1])
                )
            else:
                attrs['down-threshold'] = int(down_threshold)
        if reboot_schedule:
            attrs['reboot-schedule'] = reboot_schedule
        if data:
            with io.open(data, 'rb') as fd:
                attrs['data'] = yaml.load(stream=fd)

        if attrs:
            try:
                admin_part.create([partition, cell], attrs)
            except admin_exceptions.AlreadyExistsResult:
                admin_part.update([partition, cell], attrs)

        try:
            cli.out(formatter(admin_part.get(
                [partition, cell], dirty=bool(attrs)
            )))
        except admin_exceptions.NoSuchObjectResult:
            click.echo('Partition does not exist: %s' % partition, err=True)

    @partition.command()
    @click.argument('partition', required=False)
    @click.option('--server', required=False)
    @cli.admin.ON_EXCEPTIONS
    def get(partition, server):
        """Get partition"""
        cell = context.GLOBAL.cell
        admin_part = context.GLOBAL.admin.partition()
        admin_srv = context.GLOBAL.admin.server()

        if partition:
            # Get partition by name.
            cli.out(formatter(admin_part.get([partition, cell])))
        elif server:
            # Get partition by server name.
            srv = admin_srv.get(server)
            if srv['cell'] != cell:
                cli.bad_exit('Server does not belong to %s: %s',
                             cell, srv['cell'])

            # The server checks out (otherwise there will be exception already)
            #
            # If partition is not explicitely defined, return empty dict.
            try:
                partition_obj = admin_part.get([srv['partition'], cell])
            except admin_exceptions.NoSuchObjectResult:
                partition_obj = {}

            cli.out(formatter(partition_obj))
        else:
            cli.bad_exit('Partition or server name is required')

    @partition.command()
    @click.option('-t', '--trait', help='Trait.',
                  required=True)
    @click.option('-m', '--memory', help='Memory.',
                  default='0G', callback=cli.validate_memory)
    @click.option('-c', '--cpu', help='CPU.',
                  default='0%', callback=cli.validate_cpu)
    @click.option('-d', '--disk', help='Disk.',
                  default='0G', callback=cli.validate_disk)
    @click.option('--delete', help='Delete assignment.',
                  is_flag=True, default=False)
    @click.argument('partition')
    @cli.admin.ON_EXCEPTIONS
    def limit(trait, memory, cpu, disk, delete, partition):
        """Create or delete partition allocation limits."""
        cell = context.GLOBAL.cell
        admin_part = context.GLOBAL.admin.partition()
        part = admin_part.get([partition, cell])
        limits = part.get('limits', [])
        # remove any pre-exsting limit for this trait
        limits = [limit for limit in limits if limit['trait'] != trait]

        if not delete:
            data = {
                'trait': trait,
                'cpu': cpu,
                'memory': memory,
                'disk': disk,
            }
            limits.append(data)

        attrs = {
            'limits': limits
        }

        try:
            admin_part.update([partition, cell], attrs)
            cli.out(formatter(admin_part.get(
                [partition, cell], dirty=bool(attrs)
            )))
        except admin_exceptions.NoSuchObjectResult:
            click.echo('Partition does not exist: %s' % partition, err=True)

    @partition.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List partitions"""
        cell = context.GLOBAL.cell
        admin_cell = context.GLOBAL.admin.cell()
        partitions = admin_cell.partitions(cell)

        cli.out(formatter(partitions))

    @partition.command()
    @click.argument('label')
    @cli.admin.ON_EXCEPTIONS
    def delete(label):
        """Delete a partition"""
        cell = context.GLOBAL.cell
        admin_part = context.GLOBAL.admin.partition()

        try:
            admin_part.delete([label, cell])
        except admin_exceptions.NoSuchObjectResult:
            click.echo('Partition does not exist: %s' % label, err=True)

    del configure
    del get
    del limit
    del _list
    del delete

    return partition
