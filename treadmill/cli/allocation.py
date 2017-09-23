"""Manage Treadmill allocations.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click
import six

from treadmill import cli
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

    tenant_formatter = cli.make_formatter('tenant')
    cli.out(tenant_formatter(tenant_obj))


def _check_reserve_usage(empty, memory, cpu, disk):
    """Checks params constraints for reserve verb."""
    if empty:
        if memory:
            raise click.UsageError('Cannot combine --empty and --memory')
        if cpu:
            raise click.UsageError('Cannot combine --empty and --cpu')
        if disk:
            raise click.UsageError('Cannot combine --empty and --disk')


def _check_tenant_exists(restapi, allocation):
    """Check if tenant exist."""
    tenant_url = '/tenant/{}'.format(allocation)

    # Check if tenant exists.
    try:
        restclient.get(restapi, tenant_url).json()
    except restclient.NotFoundError:
        raise click.UsageError(
            'Allocation not found, '
            'run allocation configure {} --systems ...'.format(allocation))


def _make_allocation(restapi, allocation, env):
    """Ensure allocation exists for given environment."""
    # Make sure allocation exists for given environment.
    alloc_url = '/allocation/{}/{}'.format(allocation, env)
    try:
        restclient.post(restapi, alloc_url, payload={'environment': env})
    except restclient.AlreadyExistsError:
        pass


def init():
    """Return top level command handler."""

    alloc_formatter = cli.make_formatter('tenant')
    ctx = {}

    @click.group(name='allocation')
    @click.option('--api', required=False, help='API url to use.',
                  envvar='TREADMILL_RESTAPI')
    def allocation_grp(api):
        """Manage Treadmill allocations.

        Allocation is a group of applications that share same capacity.
        Each allocation is partitioned by environment and cell. Given
        allocation, cell and environment, users reserve capacity for their
        apps.

        Allocations form a hierarchy, so that when reservation is underused,
        extra capacity is offered to sibling apps first (by environment), and
        then up the tree for applications in parent allocations.
        """
        if api:
            ctx['api'] = api

    @allocation_grp.command(name='list')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def _list():
        """List allocations."""
        restapi = context.GLOBAL.admin_api(ctx.get('api'))
        response = restclient.get(restapi, '/tenant/')
        cli.out(alloc_formatter(response.json()))

    @allocation_grp.command()
    @click.option('-s', '--systems', help='System ID', type=cli.LIST)
    @click.argument('allocation', required=True)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def configure(allocation, systems):
        """Configure allocation.

        Allocation name is global, and is associated with list of systems.
        """
        restapi = context.GLOBAL.admin_api(ctx.get('api'))
        url = '/tenant/{}'.format(allocation)

        if systems:

            # If tenant exists, update it with new systems. If update fails
            # with resource does not exist error, try creating tenants from
            # parent to child, those that do not exist will be created with
            # provided systems.
            try:
                existing = restclient.get(restapi, url).json()
                all_systems = set(existing['systems'])
                all_systems.update(six.moves.map(int, systems))
                restclient.put(
                    restapi,
                    url,
                    payload={'systems': list(all_systems)}
                )
            except restclient.NotFoundError:
                # Create parent tenants recursively.
                #
                # If parent does not exist, it will be created with the systems
                # specified.
                parts = allocation.split(':')
                for idx in range(1, len(parts) + 1):
                    url = '/tenant/{}'.format(':'.join(parts[:idx]))

                    try:
                        existing = restclient.get(restapi, url).json()
                    except restclient.NotFoundError:
                        restclient.post(
                            restapi,
                            url,
                            payload={'systems': six.moves.map(int, systems)})

        _display_tenant(restapi, allocation)

    @allocation_grp.command()
    @click.option('-e', '--env', help='Environment.', required=True)
    @click.option('-c', '--cell', help='Treadmill cell', required=True)
    @click.option('-p', '--partition', help='Allocation partition')
    @click.option('-r', '--rank', help='Allocation rank', type=int)
    @click.option('--rank-adjustment', help='Rank adjustment', type=int)
    @click.option('--max-utilization', help='Maximum utilization', type=float)
    @click.option('--empty', help='Make empty (zero capacity) reservation.',
                  is_flag=True, default=False)
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
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    # pylint: disable=R0912
    def reserve(allocation, env, cell, partition,
                rank, rank_adjustment, max_utilization, empty,
                memory, cpu, disk):
        """Reserve capacity on the cell for given environment."""
        _check_reserve_usage(empty, memory, cpu, disk)

        restapi = context.GLOBAL.admin_api(ctx.get('api'))

        _check_tenant_exists(restapi, allocation)
        _make_allocation(restapi, allocation, env)

        data = {}
        if empty:
            data['memory'] = '0M'
            data['disk'] = '0M'
            data['cpu'] = '0%'

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

        if data:
            reservation_url = '/allocation/{}/{}/reservation/{}'.format(
                allocation, env, cell
            )

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

        _display_tenant(restapi, allocation)

    @allocation_grp.command()
    @click.option('-e', '--env', help='Environment.', required=True)
    @click.option('-c', '--cell', help='Treadmill cell', required=True)
    @click.option('--pattern', help='Application pattern.', required=True)
    @click.option('--priority', help='Assignment priority.', type=int)
    @click.option('--delete', help='Delete assignment.',
                  is_flag=True, default=False)
    @click.argument('allocation', required=True)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def assign(allocation, env, cell, pattern, priority, delete):
        """Assign application pattern:priority to the allocation.

        Application pattern must start with <PROID>. and is a glob expression.

        Environments of the proid and one specified in command line using
        --env option must match.

        Once scheduled, Treadmill scheduler will match application against all
        available patterns and assign application to a reserved capacity.

        All application assigned to a capacity are ordered by priority from
        high to low.
        """
        restapi = context.GLOBAL.admin_api(ctx.get('api'))

        _check_tenant_exists(restapi, allocation)
        _make_allocation(restapi, allocation, env)

        reservation_url = '/allocation/{}/{}/reservation/{}'.format(
            allocation, env, cell
        )

        try:
            restclient.get(restapi, reservation_url)
        except restclient.NotFoundError:
            # TODO: default partition should be resolved in API, not in CLI.
            restclient.post(restapi, reservation_url,
                            payload={'memory': '0M',
                                     'disk': '0M',
                                     'cpu': '0%',
                                     'partition': admin.DEFAULT_PARTITION})

        url = '/allocation/{}/{}/assignment/{}/{}'.format(
            allocation, env, cell, pattern
        )

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

        _display_tenant(restapi, allocation)

    @allocation_grp.command()
    @click.argument('item', required=True)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
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
