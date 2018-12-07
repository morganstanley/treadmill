"""Implementation of allocation API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from collections import defaultdict
import logging

import six

from treadmill.admin import exc as admin_exceptions
from treadmill import context
from treadmill import exc
from treadmill import schema
from treadmill import utils
from treadmill import plugin_manager

_LOGGER = logging.getLogger(__name__)

_DEFAULT_RANK = 100
_DEFAULT_PARTITION = '_default'
_DEFAULT_PRIORITY = 1


def _set_auth_resource(cls, resource):
    """Set auth resource name for CRUD methods of the class.
    """
    for method_name in ['get', 'create', 'update', 'delete']:
        method = getattr(cls, method_name, None)
        if method:
            method.auth_resource = resource


def _reservation_list(allocs, cell_allocs):
    """Combine allocations and reservations into single list.
    """
    name2alloc = {
        alloc['_id']: defaultdict(list, alloc)
        for alloc in allocs
    }
    for alloc in cell_allocs:
        name = '/'.join(alloc['_id'].split('/')[:2])
        name2alloc[name]['reservations'].append(alloc)

    return list(six.itervalues(name2alloc))


def _admin_partition():
    """Lazily return admin partition object.
    """
    return context.GLOBAL.admin.partition()


def _admin_cell_alloc():
    """Lazily return admin cell allocation object.
    """
    return context.GLOBAL.admin.cell_allocation()


def _partition_get(partition, cell):
    """Calculate free capacity for given partition.
    """
    try:
        return _admin_partition().get([partition, cell])
    except admin_exceptions.NoSuchObjectResult:
        # pretend partition has zero capacity
        return {'cpu': '0%', 'memory': '0G', 'disk': '0G', 'limits': []}


def _check_capacity(cell, allocation, rsrc):
    """
    """
    partition = rsrc['partition']
    allocs = _admin_cell_alloc().list({'cell': cell, 'partition': partition})
    part_obj = _partition_get(partition, cell)
    old_id = '{0}/{1}'.format(allocation, cell)

    # check overall allocation limit first
    free_overall = _calc_free(part_obj, allocs, old_id)
    _check_limit(free_overall, rsrc)

    # get applicable allocation limits by trait
    limits = [
        limit
        for limit in part_obj['limits']
        if limit['trait'] in rsrc['traits']
    ]

    # check trait based allocation limits
    free_by_trait = _calc_free_traits(limits, allocs, old_id)
    for limit in limits:
        _check_limit(
            free_by_trait[limit['trait']],
            rsrc,
            ' (trait: %s)' % limit['trait']
        )


def _check_limit(limit, request, extra_info=''):
    """Check capacity limit for reqested allocation.
    """
    if utils.cpu_units(request['cpu']) > limit['cpu']:
        raise exc.InvalidInputError(
            __name__, 'Not enough cpu capacity in partition.' + extra_info)

    if utils.size_to_bytes(request['disk']) > limit['disk']:
        raise exc.InvalidInputError(
            __name__, 'Not enough disk capacity in partition.' + extra_info)

    if utils.size_to_bytes(request['memory']) > limit['memory']:
        raise exc.InvalidInputError(
            __name__, 'Not enough memory capacity in partition.' + extra_info)


def _calc_free(limit, allocs, old_id):
    """Calculate free capacity in partition.

    Note: allocation with old_id is not counted.
    """
    free = {
        'cpu': utils.cpu_units(limit['cpu']),
        'disk': utils.size_to_bytes(limit['disk']),
        'memory': utils.size_to_bytes(limit['memory']),
    }

    for alloc in allocs:
        # skip allocation with old_id
        if alloc['_id'] == old_id:
            continue

        free['cpu'] -= utils.cpu_units(alloc['cpu'])
        free['disk'] -= utils.size_to_bytes(alloc['disk'])
        free['memory'] -= utils.size_to_bytes(alloc['memory'])

    return free


def _calc_free_traits(limits, allocs, old_id):
    """Calculate free capacity in partition by trait.

    Note: allocation with old_id is not counted.
    """
    free = {}
    for limit in limits:
        free[limit['trait']] = {
            'cpu': utils.cpu_units(limit['cpu']),
            'disk': utils.size_to_bytes(limit['disk']),
            'memory': utils.size_to_bytes(limit['memory']),
        }

    for alloc in allocs:
        # skip allocation with old_id
        if alloc['_id'] == old_id:
            continue

        for trait in alloc['traits']:
            if trait in free:
                free[trait]['cpu'] -= utils.cpu_units(alloc['cpu'])
                free[trait]['disk'] -= utils.size_to_bytes(alloc['cpu'])
                free[trait]['memory'] -= utils.size_to_bytes(alloc['cpu'])

    return free


def _api_plugins(plugins):
    """Return api  plugins.
    """
    if not plugins:
        return []

    plugins_ns = 'treadmill.api.allocation.plugins'
    return [
        plugin_manager.load(plugins_ns, name)
        for name in plugins
    ]


class API:
    """Treadmill Allocation REST api.
    """
    # pylint: disable=too-many-statements

    def __init__(self, plugins=None):

        self._plugins = _api_plugins(plugins)

        def _admin_alloc():
            """Lazily return admin allocation object.
            """
            return context.GLOBAL.admin.allocation()

        def _admin_tnt():
            """Lazily return admin tenant object.
            """
            return context.GLOBAL.admin.tenant()

        def _list(tenant_id=None):
            """List allocations.
            """
            if tenant_id is None:
                admin_alloc = _admin_alloc()
                admin_cell_alloc = _admin_cell_alloc()
                return _reservation_list(admin_alloc.list({}),
                                         admin_cell_alloc.list({}))
            else:
                admin_tnt = _admin_tnt()
                return _reservation_list(admin_tnt.allocations(tenant_id),
                                         admin_tnt.reservations(tenant_id))

        @schema.schema({'$ref': 'allocation.json#/resource_id'})
        def get(rsrc_id):
            """Get allocation configuration.
            """
            return _admin_alloc().get(rsrc_id)

        @schema.schema({'$ref': 'allocation.json#/resource_id'},
                       {'allOf': [{'$ref': 'allocation.json#/resource'},
                                  {'$ref': 'allocation.json#/verbs/create'}]})
        def create(rsrc_id, rsrc):
            """Create allocation.
            """
            _admin_alloc().create(rsrc_id, rsrc)
            return _admin_alloc().get(rsrc_id, dirty=True)

        @schema.schema({'$ref': 'allocation.json#/resource_id'},
                       {'allOf': [{'$ref': 'allocation.json#/resource'},
                                  {'$ref': 'allocation.json#/verbs/update'}]})
        def update(rsrc_id, rsrc):
            """Update allocation.
            """
            _admin_alloc().update(rsrc_id, rsrc)
            return _admin_alloc().get(rsrc_id, dirty=True)

        @schema.schema({'$ref': 'allocation.json#/resource_id'})
        def delete(rsrc_id):
            """Delete allocation.
            """
            _admin_alloc().delete(rsrc_id)

        class _ReservationAPI:
            """Reservation API.
            """

            def __init__(self, plugins=None):

                self._plugins = _api_plugins(plugins)

                @schema.schema({'$ref': 'reservation.json#/resource_id'})
                def get(rsrc_id):
                    """Get reservation configuration.
                    """
                    allocation, cell = rsrc_id.rsplit('/', 1)
                    inst = _admin_cell_alloc().get([cell, allocation])
                    if inst is None:
                        return inst

                    for plugin in self._plugins:
                        inst = plugin.remove_attributes(inst)

                    return inst

                @schema.schema(
                    {'$ref': 'reservation.json#/resource_id'},
                    {'allOf': [{'$ref': 'reservation.json#/resource'},
                               {'$ref': 'reservation.json#/verbs/create'}]}
                )
                def create(rsrc_id, rsrc):
                    """Create reservation.
                    """
                    allocation, cell = rsrc_id.rsplit('/', 1)
                    if 'partition' not in rsrc:
                        rsrc['partition'] = _DEFAULT_PARTITION
                    _check_capacity(cell, allocation, rsrc)
                    if 'rank' not in rsrc:
                        rsrc['rank'] = _DEFAULT_RANK

                    for plugin in self._plugins:
                        rsrc = plugin.add_attributes(rsrc_id, rsrc)

                    _admin_cell_alloc().create([cell, allocation], rsrc)
                    return _admin_cell_alloc().get(
                        [cell, allocation], dirty=True
                    )

                @schema.schema(
                    {'$ref': 'reservation.json#/resource_id'},
                    {'allOf': [{'$ref': 'reservation.json#/resource'},
                               {'$ref': 'reservation.json#/verbs/create'}]}
                )
                def update(rsrc_id, rsrc):
                    """Update reservation.
                    """
                    allocation, cell = rsrc_id.rsplit('/', 1)
                    _check_capacity(cell, allocation, rsrc)
                    admin_cell_alloc = _admin_cell_alloc()

                    cell_alloc = admin_cell_alloc.get(
                        [cell, allocation], dirty=True
                    )
                    _LOGGER.debug('Old reservation: %r', cell_alloc)

                    cell_alloc.update(rsrc)
                    _LOGGER.debug('New reservation: %r', cell_alloc)

                    admin_cell_alloc.update([cell, allocation], cell_alloc)
                    return cell_alloc

                @schema.schema({'$ref': 'reservation.json#/resource_id'})
                def delete(rsrc_id):
                    """Delete reservation.
                    """
                    allocation, cell = rsrc_id.rsplit('/', 1)
                    return _admin_cell_alloc().delete([cell, allocation])

                self.get = get
                self.create = create
                self.update = update
                self.delete = delete

                # Must be called last when all methods are set.
                _set_auth_resource(self, 'reservation')

        class _AssignmentAPI:
            """Assignment API.
            """

            def __init__(self):

                @schema.schema({'$ref': 'assignment.json#/resource_id'})
                def get(rsrc_id):
                    """Get assignment configuration.
                    """
                    # FIXME: Pattern is ignored, returns all cell assignments.
                    allocation, cell, _pattern = rsrc_id.rsplit('/', 2)
                    return _admin_cell_alloc().get(
                        [cell, allocation]).get('assignments', [])

                @schema.schema(
                    {'$ref': 'assignment.json#/resource_id'},
                    {'allOf': [{'$ref': 'assignment.json#/resource'},
                               {'$ref': 'assignment.json#/verbs/create'}]}
                )
                def create(rsrc_id, rsrc):
                    """Create assignment.
                    """
                    allocation, cell, pattern = rsrc_id.rsplit('/', 2)
                    priority = rsrc.get('priority', _DEFAULT_PRIORITY)
                    _admin_cell_alloc().create(
                        [cell, allocation],
                        {'assignments': [{'pattern': pattern,
                                          'priority': priority}]}
                    )
                    return _admin_cell_alloc().get(
                        [cell, allocation], dirty=True
                    ).get('assignments', [])

                @schema.schema(
                    {'$ref': 'assignment.json#/resource_id'},
                    {'allOf': [{'$ref': 'assignment.json#/resource'},
                               {'$ref': 'assignment.json#/verbs/update'}]}
                )
                def update(rsrc_id, rsrc):
                    """Update assignment.
                    """
                    admin_cell_alloc = _admin_cell_alloc()

                    allocation, cell, pattern = rsrc_id.rsplit('/', 2)
                    priority = rsrc.get('priority', 0)

                    assignments = admin_cell_alloc.get(
                        [cell, allocation], dirty=True
                    ).get('assignments', [])

                    assignment_attrs = {'priority': priority}
                    for assignment in assignments:
                        if assignment['pattern'] == pattern:
                            assignment.update(assignment_attrs)
                            break
                    else:
                        assignments.append(
                            {'pattern': pattern, 'priority': priority}
                        )

                    _admin_cell_alloc().update(
                        [cell, allocation],
                        {'assignments': assignments}
                    )
                    return assignments

                @schema.schema({'$ref': 'assignment.json#/resource_id'})
                def delete(rsrc_id):
                    """Delete assignment.
                    """
                    admin_cell_alloc = _admin_cell_alloc()

                    allocation, cell, pattern = rsrc_id.rsplit('/', 2)

                    assignments = admin_cell_alloc.get(
                        [cell, allocation], dirty=True
                    ).get('assignments', [])

                    new_assignments = [
                        assignment
                        for assignment in assignments
                        if assignment['pattern'] != pattern
                    ]

                    _admin_cell_alloc().update(
                        [cell, allocation],
                        {'assignments': new_assignments}
                    )

                self.get = get
                self.create = create
                self.update = update
                self.delete = delete

                # Must be called last when all methods are set.
                _set_auth_resource(self, 'assignment')

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete
        self.reservation = _ReservationAPI()
        self.assignment = _AssignmentAPI()
