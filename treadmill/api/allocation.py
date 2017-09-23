"""Implementation of allocation API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from collections import defaultdict
import logging
import ldap3

from treadmill import admin
from treadmill import authz
from treadmill import context
from treadmill import exc
from treadmill import schema
from treadmill import utils
from treadmill import plugin_manager

_LOGGER = logging.getLogger(__name__)

_DEFAULT_RANK = 100


def _set_auth_resource(cls, resource):
    """Set auth resource name for CRUD methods of the class."""
    for method_name in ['get', 'create', 'update', 'delete']:
        method = getattr(cls, method_name, None)
        if method:
            method.auth_resource = resource


def _reservation_list(allocs, cell_allocs):
    """Combine allocations and reservations into single list."""
    name2alloc = {alloc['_id']: defaultdict(list, alloc) for alloc in allocs}
    for alloc in cell_allocs:
        name = '/'.join(alloc['_id'].split('/')[:2])
        name2alloc[name]['reservations'].append(alloc)

    return name2alloc.values()


def _admin_partition():
    """Lazily return admin partition object."""
    return admin.Partition(context.GLOBAL.ldap.conn)


def _admin_cell_alloc():
    """Lazily return admin cell allocation object."""
    return admin.CellAllocation(context.GLOBAL.ldap.conn)


def _partition_free(partition, cell):
    """Calculate free capacity for given partition."""
    try:
        part_obj = _admin_partition().get([partition, cell])
    except ldap3.LDAPNoSuchObjectResult:
        # pretend partition has zero capacity
        part_obj = {'cpu': '0%', 'memory': '0G', 'disk': '0G'}

    allocs = _admin_cell_alloc().list({'cell': cell, 'partition': partition})

    cpu = utils.cpu_units(part_obj['cpu'])
    memory = utils.size_to_bytes(part_obj['memory'])
    disk = utils.size_to_bytes(part_obj['disk'])

    for alloc in allocs:
        cpu -= utils.cpu_units(alloc['cpu'])
        memory -= utils.size_to_bytes(alloc['memory'])
        disk -= utils.size_to_bytes(alloc['disk'])

    return {'cpu': cpu, 'memory': memory, 'disk': disk}


def _check_capacity(cell, allocation, rsrc):
    """Check that there is enough free space for the allocation."""
    try:
        old = _admin_cell_alloc().get([cell, allocation])
        if old['partition'] != rsrc['partition']:
            old = {'cpu': '0%', 'memory': '0G', 'disk': '0G'}
    except ldap3.LDAPNoSuchObjectResult:
        old = {'cpu': '0%', 'memory': '0G', 'disk': '0G'}

    free = _partition_free(rsrc['partition'], cell)

    if (free['cpu'] + utils.cpu_units(old['cpu']) <
            utils.cpu_units(rsrc['cpu'])):
        raise exc.InvalidInputError(
            __name__, 'Not enough cpu capacity in partition.')

    if (free['memory'] + utils.size_to_bytes(old['memory']) <
            utils.size_to_bytes(rsrc['memory'])):
        raise exc.InvalidInputError(
            __name__, 'Not enough memory capacity in partition.')

    if (free['disk'] + utils.size_to_bytes(old['disk']) <
            utils.size_to_bytes(rsrc['disk'])):
        raise exc.InvalidInputError(
            __name__, 'Not enough disk capacity in partition.')


def _api_plugins(initialized):
    """Return api  plugins."""
    if initialized is not None:
        return initialized

    plugins_ns = 'treadmill.api.allocation.plugins'
    return [
        plugin_manager.load(plugins_ns, name)
        for name in context.GLOBAL.get('api.allocation.plugins', [])
    ]


class API(object):
    """Treadmill Allocation REST api."""

    def __init__(self):

        def _admin_alloc():
            """Lazily return admin allocation object."""
            return admin.Allocation(context.GLOBAL.ldap.conn)

        def _admin_tnt():
            """Lazily return admin tenant object."""
            return admin.Tenant(context.GLOBAL.ldap.conn)

        def _list(tenant_id=None):
            """List allocations."""
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
            """Get allocation configuration."""
            return _admin_alloc().get(rsrc_id)

        @schema.schema({'$ref': 'allocation.json#/resource_id'},
                       {'allOf': [{'$ref': 'allocation.json#/resource'},
                                  {'$ref': 'allocation.json#/verbs/create'}]})
        def create(rsrc_id, rsrc):
            """Create allocation."""
            _admin_alloc().create(rsrc_id, rsrc)
            return _admin_alloc().get(rsrc_id)

        @schema.schema({'$ref': 'allocation.json#/resource_id'},
                       {'allOf': [{'$ref': 'allocation.json#/resource'},
                                  {'$ref': 'allocation.json#/verbs/update'}]})
        def update(rsrc_id, rsrc):
            """Update allocation."""
            _admin_alloc().update(rsrc_id, rsrc)
            return _admin_alloc().get(rsrc_id)

        @schema.schema({'$ref': 'allocation.json#/resource_id'})
        def delete(rsrc_id):
            """Delete allocation."""
            _admin_alloc().delete(rsrc_id)
            return None

        class _ReservationAPI(object):
            """Reservation API."""

            def __init__(self):

                self.plugins = None

                @schema.schema({'$ref': 'reservation.json#/resource_id'})
                def get(rsrc_id):
                    """Get reservation configuration."""
                    allocation, cell = rsrc_id.rsplit('/', 1)
                    inst = _admin_cell_alloc().get([cell, allocation])
                    if inst is None:
                        return inst

                    self.plugins = _api_plugins(self.plugins)
                    for plugin in self.plugins:
                        inst = plugin.remove_attributes(inst)

                    return inst

                @schema.schema(
                    {'$ref': 'reservation.json#/resource_id'},
                    {'allOf': [{'$ref': 'reservation.json#/resource'},
                               {'$ref': 'reservation.json#/verbs/create'}]}
                )
                def create(rsrc_id, rsrc):
                    """Create reservation."""
                    allocation, cell = rsrc_id.rsplit('/', 1)
                    _check_capacity(cell, allocation, rsrc)
                    if 'rank' not in rsrc:
                        rsrc['rank'] = _DEFAULT_RANK

                    self.plugins = _api_plugins(self.plugins)
                    for plugin in self.plugins:
                        rsrc = plugin.add_attributes(rsrc_id, rsrc)

                    _admin_cell_alloc().create([cell, allocation], rsrc)
                    return _admin_cell_alloc().get([cell, allocation])

                @schema.schema(
                    {'$ref': 'reservation.json#/resource_id'},
                    {'allOf': [{'$ref': 'reservation.json#/resource'},
                               {'$ref': 'reservation.json#/verbs/create'}]}
                )
                def update(rsrc_id, rsrc):
                    """Create reservation."""
                    allocation, cell = rsrc_id.rsplit('/', 1)
                    _check_capacity(cell, allocation, rsrc)
                    _admin_cell_alloc().update([cell, allocation], rsrc)
                    return _admin_cell_alloc().get([cell, allocation])

                @schema.schema({'$ref': 'reservation.json#/resource_id'})
                def delete(rsrc_id):
                    """Delete reservation."""
                    allocation, cell = rsrc_id.rsplit('/', 1)
                    return _admin_cell_alloc().delete([cell, allocation])

                self.get = get
                self.create = create
                self.update = update
                self.delete = delete

                # Must be called last when all methods are set.
                _set_auth_resource(self, 'reservation')

        class _AssignmentAPI(object):
            """Assignment API."""

            def __init__(self):

                @schema.schema({'$ref': 'assignment.json#/resource_id'})
                def get(rsrc_id):
                    """Get assignment configuration."""
                    allocation, cell, _pattern = rsrc_id.rsplit('/', 2)
                    return _admin_cell_alloc().get(
                        [cell, allocation]).get('assignments', [])

                @schema.schema(
                    {'$ref': 'assignment.json#/resource_id'},
                    {'allOf': [{'$ref': 'assignment.json#/resource'},
                               {'$ref': 'assignment.json#/verbs/create'}]}
                )
                def create(rsrc_id, rsrc):
                    """Create assignment."""
                    allocation, cell, pattern = rsrc_id.rsplit('/', 2)
                    priority = rsrc.get('priority', 0)
                    _admin_cell_alloc().create(
                        [cell, allocation],
                        {'assignments': [{'pattern': pattern,
                                          'priority': priority}]}
                    )
                    return _admin_cell_alloc().get(
                        [cell, allocation]).get('assignments', [])

                @schema.schema(
                    {'$ref': 'assignment.json#/resource_id'},
                    {'allOf': [{'$ref': 'assignment.json#/resource'},
                               {'$ref': 'assignment.json#/verbs/update'}]}
                )
                def update(rsrc_id, rsrc):
                    """Update assignment."""
                    allocation, cell, pattern = rsrc_id.rsplit('/', 2)
                    priority = rsrc.get('priority', 0)
                    _admin_cell_alloc().update(
                        [cell, allocation],
                        {'assignments': [{'pattern': pattern,
                                          'priority': priority}]}
                    )
                    return _admin_cell_alloc().get(
                        [cell, allocation]).get('assignments', [])

                @schema.schema({'$ref': 'assignment.json#/resource_id'})
                def delete(rsrc_id):
                    """Delete assignment."""
                    allocation, cell, pattern = rsrc_id.rsplit('/', 2)
                    _admin_cell_alloc().update(
                        [cell, allocation],
                        {'assignments': [{'pattern': pattern,
                                          'priority': 0,
                                          '_delete': True}]}
                    )
                    return None

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


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
