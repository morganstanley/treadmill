"""Implementation of treadmill admin ldap CLI allocation plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from collections import defaultdict

import click
from treadmill.admin import exc as admin_exceptions

from treadmill import cli
from treadmill import context

_DEFAULT_RANK = 100
_DEFAULT_PARTITION = '_default'
_DEFAULT_PRIORITY = 1


def _check_tenant_exists(tenant):
    """Check if tenant exist."""
    admin_tenant = context.GLOBAL.admin.tenant()
    tenant_obj = None
    try:
        tenant_obj = admin_tenant.get(tenant)
    except admin_exceptions.NoSuchObjectResult:
        raise click.UsageError(
            'Allocation {} does not exist'.format(tenant))
    return tenant_obj


def _display_tenant(tenant):
    """Display allocations for the given tenant."""
    tenant_obj = _check_tenant_exists(tenant)
    admin_tenant = context.GLOBAL.admin.tenant()
    allocs = admin_tenant.allocations(tenant)
    cell_allocs = admin_tenant.reservations(tenant)
    name2alloc = {alloc['_id']: defaultdict(list, alloc)
                  for alloc in allocs}

    for alloc in cell_allocs:
        name = '/'.join(alloc['_id'].split('/')[:2])
        name2alloc[name]['reservations'].append(alloc)

    allocations_obj = list(name2alloc.values())

    tenant_obj['allocations'] = allocations_obj

    tenant_formatter = cli.make_formatter('tenant')
    cli.out(tenant_formatter(tenant_obj))


def _make_allocation(tenant, env):
    """Ensure allocation exists for given environment."""
    admin_alloc = context.GLOBAL.admin.allocation()
    try:
        admin_alloc.create('{}/{}'.format(tenant, env),
                           {'environment': env})
    except admin_exceptions.AlreadyExistsResult:
        pass


def init():
    """Configures allocations CLI group"""
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements
    formatter = cli.make_formatter('tenant')

    @click.group()
    def allocation():
        """Manage allocations.
        """

    @allocation.command()
    @click.option('-s', '--systems', help='Specify the System IDs',
                  type=cli.LIST)
    @click.option('--add-systems', 'add_systems',
                  help='Add System IDs to the exiting systems',
                  type=cli.LIST)
    @click.option('--remove-systems', 'remove_systems',
                  help='Remove System IDs to the exiting systems',
                  type=cli.LIST)
    @click.option('--delete', help='Delete the Allocation',
                  is_flag=True, default=False)
    @click.argument('allocation')
    @cli.admin.ON_EXCEPTIONS
    def configure(systems, add_systems,
                  remove_systems, delete, allocation):
        """Create, get or modify allocation configuration"""
        admin_tenant = context.GLOBAL.admin.tenant()
        try:
            existing = admin_tenant.get(allocation)
            if delete:
                admin_tenant.delete(allocation)
            elif systems or add_systems or remove_systems:
                # remove duplicates from cli input
                # or it returns error from create/update
                all_systems = set(str(sys) for sys in existing['systems'])
                if systems:
                    all_systems = set(systems)
                if add_systems:
                    all_systems.update(add_systems)
                if remove_systems:
                    if set(remove_systems).issubset(all_systems):
                        all_systems.difference_update(remove_systems)
                    else:
                        raise click.UsageError(
                            "removing-systems {} ".format(remove_systems) +
                            "contain system(s) does not exist")
                admin_tenant.update(allocation,
                                    {'systems':
                                     sorted(all_systems)})
        except admin_exceptions.NoSuchObjectResult:
            if systems:
                all_systems = set(systems)
                admin_tenant.create(allocation,
                                    {'systems':
                                     sorted(all_systems)})
            else:
                raise click.UsageError(
                    'Allocation {} does not exist'.format(allocation))

        _display_tenant(allocation)

    @allocation.command()
    @click.option('-m', '--memory', help='Memory.',
                  callback=cli.validate_memory)
    @click.option('-c', '--cpu', help='CPU.',
                  callback=cli.validate_cpu)
    @click.option('-d', '--disk', help='Disk.',
                  callback=cli.validate_disk)
    @click.option('-r', '--rank', help='Rank.', type=int)
    @click.option('-a', '--rank-adjustment', help='Rank adjustment.', type=int)
    @click.option('-u', '--max-utilization',
                  help='Max utilization.', type=float)
    @click.option('-t', '--traits', help='Allocation traits', type=cli.LIST)
    @click.option('-p', '--partition', help='Allocation partition')
    @click.option('--cell', help='Cell.', required=True)
    @click.option('--env', help='Environment.',
                  type=click.Choice(['dev', 'qa', 'uat', 'prod']),
                  required=True)
    @click.option('--delete', help='Delete reservation',
                  default=False, is_flag=True)
    @click.argument('allocation')
    @cli.admin.ON_EXCEPTIONS
    def reserve(allocation, cell, env, memory, cpu, disk, rank,
                rank_adjustment, max_utilization, traits, partition, delete):
        # pylint: disable=R0915
        """Reserve capacity on a given cell"""
        _check_tenant_exists(allocation)
        admin_cell_alloc = context.GLOBAL.admin.cell_allocation()
        allocation_env = allocation + '/' + env
        if delete:
            admin_cell_alloc.delete([cell, allocation_env])
            return

        _make_allocation(allocation, env)

        data = {}
        if memory:
            data['memory'] = memory
        if cpu:
            data['cpu'] = cpu
        if disk:
            data['disk'] = disk
        if partition:
            if partition == '-':
                partition = _DEFAULT_PARTITION
            data['partition'] = partition
        if rank is not None:
            data['rank'] = rank
        if rank_adjustment is not None:
            data['rank_adjustment'] = rank_adjustment
        if max_utilization is not None:
            data['max_utilization'] = max_utilization
        if traits:
            data['traits'] = cli.combine(traits)

        try:
            existing = admin_cell_alloc.get([cell, allocation_env])
            if data:
                admin_cell_alloc.update([cell, allocation_env], data)

        except admin_exceptions.NoSuchObjectResult:
            if memory is None:
                data['memory'] = '0M'
            if cpu is None:
                data['cpu'] = '0%'
            if disk is None:
                data['disk'] = '0M'
            if partition is None:
                data['partition'] = _DEFAULT_PARTITION
            if rank is None:
                data['rank'] = _DEFAULT_RANK
            admin_cell_alloc.create([cell, allocation_env], data)

        _display_tenant(allocation)

    @allocation.command()
    @click.option('--pattern', help='Application name pattern.',
                  required=True)
    @click.option('--priority', help='Assigned priority.', type=int)
    @click.option('--cell', help='Cell.', required=True)
    @click.option('--env', help='Environment.',
                  type=click.Choice(['dev', 'qa', 'uat', 'prod']),
                  required=True)
    @click.option('--delete', help='Delete assignment.',
                  is_flag=True, default=False)
    @click.argument('allocation')
    @cli.admin.ON_EXCEPTIONS
    def assign(allocation, cell, env, priority, pattern, delete):
        """Manage application assignments"""
        admin_cell_alloc = context.GLOBAL.admin.cell_allocation()
        allocation_env = allocation + '/' + env
        _check_tenant_exists(allocation)
        _make_allocation(allocation, env)

        assignment = {'pattern': pattern}
        assignment['priority'] = priority \
            if priority is not None else _DEFAULT_PRIORITY
        try:
            existing = admin_cell_alloc.get([cell, allocation_env])
            assignments = existing.get('assignments', [])

            new_assignments = [
                old_assignment
                for old_assignment in assignments
                if old_assignment['pattern'] != pattern
            ]
            if not delete:
                new_assignments.append(assignment)

            admin_cell_alloc.update([cell, allocation_env],
                                    {'assignments': new_assignments})
        except admin_exceptions.NoSuchObjectResult:
            if not delete:
                data = {}
                data['cpu'] = '0%'
                data['memory'] = '0M'
                data['disk'] = '0M'
                data['partition'] = _DEFAULT_PARTITION
                data['rank'] = _DEFAULT_RANK
                data = {'assignments': [assignment]}
                admin_cell_alloc.create([cell, allocation_env], data)

        _display_tenant(allocation)

    @allocation.command(name='list')
    @cli.admin.ON_EXCEPTIONS
    def _list():
        """List configured allocations"""
        admin_tenant = context.GLOBAL.admin.tenant()
        cli.out(formatter(admin_tenant.list({})))

    @allocation.command()
    @click.argument('item', required=True)
    @cli.admin.ON_EXCEPTIONS
    def delete(item):
        """Delete an allocation/reservation(s)"""
        path = item.split('/')
        if len(path) == 1:
            admin_tenant = context.GLOBAL.admin.tenant()
            admin_tenant.delete(item)
        elif len(path) == 2:
            admin_alloc = context.GLOBAL.admin.allocation()
            admin_alloc.delete(item)
        elif len(path) == 3:
            admin_cell_alloc = context.GLOBAL.admin.cell_allocation()
            admin_cell_alloc.delete(list(reversed(item.rsplit('/', 1))))
        else:
            # error
            click.echo('Wrong format: {}'.format(item), err=True)

    del assign
    del reserve
    del delete
    del _list
    del configure

    return allocation
