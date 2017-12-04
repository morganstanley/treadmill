"""Implementation of treadmill admin ldap CLI allocation plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click
from ldap3.core import exceptions as ldap_exceptions

from treadmill import admin
from treadmill import cli
from treadmill import context


def init():
    """Configures allocations CLI group"""
    # "too many branches" pylint warning.
    #
    # pylint: disable=R0912
    formatter = cli.make_formatter('allocation')

    @click.group()
    def allocation():
        """Manage allocations"""
        pass

    @allocation.command()
    @click.option('-e', '--environment', help='Environment',
                  type=click.Choice(['dev', 'qa', 'uat', 'prod']))
    @click.argument('allocation')
    @cli.admin.ON_EXCEPTIONS
    def configure(environment, allocation):
        """Create, get or modify allocation configuration"""
        admin_alloc = admin.Allocation(context.GLOBAL.ldap.conn)

        attrs = {}
        if environment:
            attrs['environment'] = environment

        if attrs:
            try:
                admin_alloc.create(allocation, attrs)
            except ldap_exceptions.LDAPEntryAlreadyExistsResult:
                admin_alloc.update(allocation, attrs)

        try:
            cli.out(formatter(admin_alloc.get(allocation)))
        except ldap_exceptions.LDAPNoSuchObjectResult:
            click.echo('Allocation does not exist: %s' % allocation, err=True)

    @allocation.command()
    @click.option('-m', '--memory', help='Memory.',
                  callback=cli.validate_memory)
    @click.option('-c', '--cpu', help='CPU.',
                  callback=cli.validate_cpu)
    @click.option('-d', '--disk', help='Disk.',
                  callback=cli.validate_disk)
    @click.option('-r', '--rank', help='Rank.', type=int, default=100)
    @click.option('-a', '--rank-adjustment', help='Rank adjustment.', type=int)
    @click.option('-u', '--max-utilization',
                  help='Max utilization.', type=float)
    @click.option('-t', '--traits', help='Allocation traits', type=cli.LIST)
    @click.option('-p', '--partition', help='Allocation partition')
    @click.option('--cell', help='Cell.', required=True)
    @click.option('--delete', help='Delete reservation', required=False,
                  default=False, is_flag=True)
    @click.argument('allocation')
    @cli.admin.ON_EXCEPTIONS
    def reserve(allocation, cell, memory, cpu, disk, rank, rank_adjustment,
                max_utilization, traits, partition, delete):
        """Reserve capacity on a given cell"""
        admin_cell_alloc = admin.CellAllocation(context.GLOBAL.ldap.conn)
        if delete:
            return admin_cell_alloc.delete([cell, allocation])

        data = {}
        if memory:
            data['memory'] = memory
        if cpu:
            data['cpu'] = cpu
        if disk:
            data['disk'] = disk
        if rank is not None:
            data['rank'] = rank
        if rank_adjustment is not None:
            data['rank_adjustment'] = rank_adjustment
        if max_utilization is not None:
            data['max_utilization'] = max_utilization
        if traits:
            data['traits'] = cli.combine(traits)
        if partition:
            if partition == '-':
                partition = None
            data['partition'] = partition

        try:
            admin_cell_alloc.create([cell, allocation], data)
        except ldap_exceptions.LDAPEntryAlreadyExistsResult:
            admin_cell_alloc.update([cell, allocation], data)

        try:
            admin_alloc = admin.Allocation(context.GLOBAL.ldap.conn)
            cli.out(formatter(admin_alloc.get(allocation)))
        except ldap_exceptions.LDAPNoSuchObjectResult:
            click.echo('Allocation does not exist: %s' % allocation, err=True)

    @allocation.command()
    @click.option('--pattern', help='Application name pattern.',
                  required=True)
    @click.option('--priority', help='Assigned priority.', type=int,
                  required=True)
    @click.option('--cell', help='Cell.', required=True)
    @click.option('--delete', help='Delete assignment.',
                  is_flag=True, default=False)
    @click.argument('allocation')
    @cli.admin.ON_EXCEPTIONS
    def assign(allocation, cell, priority, pattern, delete):
        """Manage application assignments"""
        admin_cell_alloc = admin.CellAllocation(context.GLOBAL.ldap.conn)
        assignment = {'pattern': pattern, 'priority': priority}
        if delete:
            assignment['_delete'] = True

        data = {'assignments': [assignment]}
        if delete:
            admin_cell_alloc.update([cell, allocation], data)
        else:
            try:
                admin_cell_alloc.create([cell, allocation], data)
            except ldap_exceptions.LDAPEntryAlreadyExistsResult:
                admin_cell_alloc.update([cell, allocation], data)

        try:
            admin_alloc = admin.Allocation(context.GLOBAL.ldap.conn)
            cli.out(formatter(admin_alloc.get(allocation)))
        except ldap_exceptions.LDAPNoSuchObjectResult:
            click.echo('Allocation does not exist: %s' % allocation, err=True)

    @allocation.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List configured allocations"""
        admin_alloc = admin.Allocation(context.GLOBAL.ldap.conn)
        cli.out(formatter(admin_alloc.list({})))

    @allocation.command()
    @click.argument('allocation')
    @cli.admin.ON_EXCEPTIONS
    def delete(allocation):
        """Delete an allocation"""
        admin_alloc = admin.Allocation(context.GLOBAL.ldap.conn)
        try:
            admin_alloc.delete(allocation)
        except ldap_exceptions.LDAPNoSuchObjectResult:
            click.echo('Allocation does not exist: %s' % allocation, err=True)

    del assign
    del reserve
    del delete
    del _list
    del configure

    return allocation
