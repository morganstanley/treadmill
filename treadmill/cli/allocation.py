"""Manage Treadmill allocations."""


import logging

import click

from .. import cli
from treadmill import restclient
from treadmill import context
from treadmill import admin


_DEFAULT_PRIORITY = 1

_LOGGER = logging.getLogger(__name__)


def _display_tenant(restapi, tenant):
    """Display allocations for the given tenant."""
    tenant_url = '/tenant/%s' % tenant
    alloc_url = '/allocation/%s' % tenant

    tenant_obj = restclient.get(restapi, tenant_url).json()
    allocations_obj = restclient.get(restapi, alloc_url).json()

    tenant_obj['allocations'] = allocations_obj

    tenant_formatter = cli.make_formatter(cli.TenantPrettyFormatter)
    cli.out(tenant_formatter(tenant_obj))


def _display_alloc(restapi, allocation):
    """Display allocation."""
    alloc_url = '/allocation/%s' % allocation
    allocation_obj = restclient.get(restapi, alloc_url).json()
    alloc_formatter = cli.make_formatter(cli.AllocationPrettyFormatter)
    cli.out(alloc_formatter(allocation_obj))


def init():
    """Return top level command handler."""

    alloc_formatter = cli.make_formatter(cli.AllocationPrettyFormatter)
    ctx = {}

    @click.group(name='allocation')
    @click.option('--api', required=False, help='API url to use.',
                  envvar='TREADMILL_RESTAPI')
    def allocation_grp(api):
        """Configure Treadmill allocations."""
        if api:
            ctx['api'] = api

    @allocation_grp.command(name='list')
    @cli.ON_REST_EXCEPTIONS
    def _list():
        """Configure allocation tenant."""
        restapi = context.GLOBAL.admin_api(ctx.get('api'))
        response = restclient.get(restapi, '/allocation/')
        cli.out(alloc_formatter(response.json()))

    @allocation_grp.command()
    @click.option('-s', '--systems', help='System ID', type=cli.LIST)
    @click.option('-e', '--env', help='Environment')
    @click.option('-n', '--name', help='Allocation name')
    @click.argument('tenant', required=True)
    @cli.ON_REST_EXCEPTIONS
    def configure(tenant, systems, name, env):
        """Configure allocation tenant."""
        restapi = context.GLOBAL.admin_api(ctx.get('api'))
        tenant_url = '/tenant/%s' % tenant

        if systems:
            try:
                existing = restclient.get(restapi, tenant_url).json()
                all_systems = set(existing['systems'])
                all_systems.update(map(int, systems))
                restclient.put(
                    restapi,
                    tenant_url,
                    payload={'systems': list(all_systems)}
                )
            except restclient.NotFoundError:
                restclient.post(
                    restapi,
                    tenant_url,
                    payload={'systems': map(int, systems)}
                )

        if env:
            if name is None:
                name = env

            alloc_url = '/allocation/%s/%s' % (tenant, name)
            try:
                restclient.post(restapi, alloc_url,
                                payload={'environment': env})
            except restclient.AlreadyExistsError:
                pass

        _display_tenant(restapi, tenant)

    @allocation_grp.command()
    @click.option('-c', '--cell', help='Treadmill cell')
    @click.option('-p', '--partition', help='Allocation partition')
    @click.option('-r', '--rank', help='Allocation rank', type=int)
    @click.option('--rank-adjustment', help='Rank adjustment', type=int)
    @click.option('--max-utilization', help='Maximum utilization', type=float)
    @click.option('--memory', help='Memory demand.',
                  metavar='G|M',
                  callback=cli.validate_memory)
    @click.option('--cpu', help='CPU demand, %.',
                  metavar='XX%',
                  callback=cli.validate_cpu)
    @click.option('--disk', help='Disk demand.',
                  metavar='G|M',
                  callback=cli.validate_disk)
    @click.argument('allocation', required=True)
    @cli.ON_REST_EXCEPTIONS
    def reserve(allocation, cell, partition,  # pylint: disable=R0912
                rank, rank_adjustment, max_utilization, memory, cpu, disk):
        """Reserve capacity on the cell."""
        restapi = context.GLOBAL.admin_api(ctx.get('api'))

        if (cell is None and
                any([memory, cpu, disk, rank is not None, partition])):
            raise click.UsageError(
                'Must specify cell with modifying reservation.')

        if cell:
            # Create reservation for the given cell.
            reservation_url = '/allocation/%s/reservation/%s' % (allocation,
                                                                 cell)

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
            if partition:
                data['partition'] = partition

            try:
                existing = restclient.get(restapi, reservation_url).json()
                # TODO: need cleaner way of deleting attributes that are not
                #       valid for update. It is a hack.
                for attr in existing.keys():
                    if (attr not in
                            ['memory', 'cpu', 'disk', 'partition']):
                        del existing[attr]

                existing.update(data)
                restclient.put(restapi, reservation_url, payload=existing)

            except restclient.NotFoundError:
                # some attributes need default values when creating
                if not partition:
                    data['partition'] = admin.DEFAULT_PARTITION

                restclient.post(restapi, reservation_url, payload=data)

        _display_alloc(restapi, allocation)

    @allocation_grp.command()
    @click.option('-c', '--cell', help='Treadmill cell', required=True)
    @click.option('--pattern', help='Application pattern.', required=True)
    @click.option('--priority', help='Assignment priority.', type=int)
    @click.option('--delete', help='Delete assignment.',
                  is_flag=True, default=False)
    @click.argument('allocation', required=True)
    @cli.ON_REST_EXCEPTIONS
    def assign(allocation, cell, pattern, priority, delete):
        """Assign application pattern:priority to the allocation."""
        restapi = context.GLOBAL.admin_api(ctx.get('api'))
        url = '/allocation/%s/assignment/%s/%s' % (allocation,
                                                   cell,
                                                   pattern)

        if delete:
            restclient.delete(restapi, url)
        else:
            default_prio = None
            existing = restclient.get(restapi, url).json()
            for assignment in existing:
                if assignment['pattern'] == pattern:
                    default_prio = assignment['priority']
            if default_prio is None:
                default_prio = _DEFAULT_PRIORITY

            data = {'priority': priority if priority else default_prio}
            restclient.put(restapi, url, payload=data)

        _display_alloc(restapi, allocation)

    @allocation_grp.command()
    @click.argument('item', required=True)
    @cli.ON_REST_EXCEPTIONS
    def delete(item):
        """Delete a tenant/allocation/reservation."""
        restapi = context.GLOBAL.admin_api(ctx.get('api'))

        path = item.split('/')
        if len(path) == 1:
            # delete a tenant
            url = '/tenant/%s' % item
            restclient.delete(restapi, url)
        elif len(path) == 2:
            # delete an allocation
            url = '/allocation/%s' % item
            restclient.delete(restapi, url)
        elif len(path) == 3:
            # delete a reservation
            url = '/allocation/%s/%s/reservation/%s' % (path[0],
                                                        path[1],
                                                        path[2])
            restclient.delete(restapi, url)
        else:
            # error
            click.echo('Wrong format: %s' % item, err=True)

    del assign
    del reserve
    del configure
    del _list
    del delete

    return allocation_grp
