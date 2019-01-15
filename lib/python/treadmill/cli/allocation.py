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
from treadmill import context
from treadmill import restclient


_LOGGER = logging.getLogger(__name__)


def _display_tenant(restapi, tenant):
    """Display allocations for the given tenant."""
    tenant_url = '/tenant/{}'.format(tenant)
    alloc_url = '/allocation/{}'.format(tenant)

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
    # pylint: disable=too-many-statements

    alloc_formatter = cli.make_formatter('tenant')

    @click.group(name='allocation')
    @click.option('--api-service-principal', required=False,
                  envvar='TREADMILL_API_SERVICE_PRINCIPAL',
                  callback=cli.handle_context_opt,
                  help='API service principal for SPNEGO auth (default HTTP)',
                  expose_value=False)
    def allocation_grp():
        """Manage Treadmill allocations.

        Allocation is a group of applications that share same capacity.
        Each allocation is partitioned by environment and cell. Given
        allocation, cell and environment, users reserve capacity for their
        apps.

        Allocations form a hierarchy, so that when reservation is underused,
        extra capacity is offered to sibling apps first (by environment), and
        then up the tree for applications in parent allocations.
        """

    @allocation_grp.command(name='list')
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def _list():
        """List allocations."""
        restapi = context.GLOBAL.admin_api()
        response = restclient.get(restapi, '/tenant/')
        cli.out(alloc_formatter(response.json()))

    @allocation_grp.command()
    @click.option('--set', 'set_', help='If specified then the allocation\'s'
                  ' system id(s) will be replaced instead of updated',
                  is_flag=True, default=False)
    @click.option('-s', '--systems', help='System ID', type=cli.LIST)
    @click.argument('allocation', required=True)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def configure(allocation, systems, set_):
        """Configure allocation.

        Allocation name is global, and is associated with list of systems.
        """
        restapi = context.GLOBAL.admin_api()
        url = '/tenant/{}'.format(allocation)

        if systems:

            # If tenant exists, update or replace it with new systems.
            # If update fails with resource does not exist error, try creating
            # tenants from parent to child, those that do not exist will be
            # created with provided systems.
            try:
                existing = restclient.get(restapi, url).json()
                all_systems = set(six.moves.map(int, systems))
                # if the system ids have to be extended instead of replaced
                if not set_:
                    all_systems.update(existing['systems'])
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
                            payload={
                                'systems': list(six.moves.map(int, systems))
                            })

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
    @click.option('--traits', help='Requested traits.', type=cli.LIST)
    @click.option('--delete', help='Delete reservation.',
                  is_flag=True, default=False)
    @click.argument('allocation', required=True)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    # pylint: disable=R0912,too-many-arguments,too-many-locals
    def reserve(allocation, env, cell, partition,
                rank, rank_adjustment, max_utilization, empty,
                memory, cpu, disk, traits, delete):

        """Reserve capacity on the cell for given environment."""
        _check_reserve_usage(empty, memory, cpu, disk)

        restapi = context.GLOBAL.admin_api()

        _check_tenant_exists(restapi, allocation)

        if delete:
            url = '/allocation/{}/{}/reservation/{}'.format(
                allocation,
                env,
                cell)
            restclient.delete(restapi, url)
            _display_tenant(restapi, allocation)
            return

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
        if partition:
            data['partition'] = partition
        if rank is not None:
            data['rank'] = rank
        if rank_adjustment is not None:
            data['rank_adjustment'] = rank_adjustment
        if max_utilization is not None:
            data['max_utilization'] = max_utilization

        reservation_url = '/allocation/{}/{}/reservation/{}'.format(
            allocation, env, cell
        )

        try:
            existing = restclient.get(restapi, reservation_url).json()
            if data:
                # To meet the json schema required in create
                if 'memory' not in data:
                    data['memory'] = existing['memory']
                if 'cpu' not in data:
                    data['cpu'] = existing['cpu']
                if 'disk' not in data:
                    data['disk'] = existing['disk']
                if 'partition' not in data:
                    data['partition'] = existing['partition']
                if traits:
                    cli.error('cannot modify traits on existing reservation.')
                restclient.put(restapi, reservation_url, payload=data)
        except restclient.NotFoundError:
            if traits:
                data['traits'] = cli.combine(traits)
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
    # pylint: disable=too-many-arguments
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
        restapi = context.GLOBAL.admin_api()

        _check_tenant_exists(restapi, allocation)
        _make_allocation(restapi, allocation, env)

        reservation_url = '/allocation/{}/{}/reservation/{}'.format(
            allocation, env, cell
        )

        try:
            restclient.get(restapi, reservation_url)
        except restclient.NotFoundError:
            restclient.post(restapi, reservation_url,
                            payload={'memory': '0M',
                                     'disk': '0M',
                                     'cpu': '0%'})

        url = '/allocation/{}/{}/assignment/{}/{}'.format(
            allocation, env, cell, pattern
        )

        if delete:
            restclient.delete(restapi, url)
        else:
            data = {}
            if priority:
                data['priority'] = priority
            # assign is always put
            # because assign and reserve belong to the same ldap obj
            restclient.put(restapi, url, payload=data)

            _display_tenant(restapi, allocation)

    def _check_reservation(restapi, tenant):
        """ check whether there are reservations
        """
        try:
            url = '/allocation/{0}'.format(tenant)
            allocs = restclient.get(restapi, url).json()
            reservations = [d['_id'] for d in allocs]
            if reservations:
                cli.out('There are undeleted reservations under this '
                        "allocation {}, please delete them first: ".format(
                            tenant))
                for rev in reservations:
                    cli.out(rev)
            return reservations
        except restclient.NotFoundError:
            # when the user is trying to delete a non-existing tenant
            raise click.UsageError(
                'Allocation {} does not exist, '.format(tenant))

    def _tenant_empty(restapi, tenant):
        """Check whether there are reservations or suballocations under this
        tenant.
        """
        # check whether there are subtenants(suballocations)
        response = restclient.get(restapi, '/tenant/').json()
        # all suballocations should be named as '<allocation>:*'
        suballocations = [d['tenant'] for d in response
                          if d['tenant'].startswith(tenant + ':')]
        if suballocations:
            cli.out('There are undeleted suballocations under this '
                    "allocation {}, please delete them first: ".format(
                        tenant))
            for sub in suballocations:
                cli.out(sub)
            return suballocations

        # The case there is no subtenant(suballocation)
        return _check_reservation(restapi, tenant)

    @allocation_grp.command()
    @click.argument('item', required=True)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def delete(item):
        """Delete a tenant/allocation/reservation."""
        restapi = context.GLOBAL.admin_api()

        path = item.split('/')
        if len(path) == 1:
            # delete a tenant
            if not _tenant_empty(restapi, item):
                url = '/tenant/{}'.format(item)
                restclient.delete(restapi, url)
        elif len(path) == 2:
            # delete all reservations and all patterns
            url = '/allocation/{}'.format(item)
            restclient.delete(restapi, url)
        elif len(path) == 3:
            # delete a reservation
            # API automatically clears the pattern under it
            url = '/allocation/{}/{}/reservation/{}'.format(
                path[0],
                path[1],
                path[2])
            restclient.delete(restapi, url)
        else:
            # error
            click.echo('Wrong format: {}'.format(item), err=True)

    del assign
    del reserve
    del configure
    del _list
    del delete

    return allocation_grp
