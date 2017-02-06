"""Implementation of allocation API."""


from .. import admin
from .. import authz
from .. import context
from .. import schema


def _set_auth_resource(cls, resource):
    """Set auth resource name for CRUD methods of the class."""
    for method_name in ['get', 'create', 'update', 'delete']:
        method = getattr(cls, method_name, None)
        if method:
            method.auth_resource = resource


def _reservation_list(allocs, cell_allocs):
    """Combine allocations and reservations into single list."""
    alloc2env = {alloc['_id']: alloc['environment'] for alloc in allocs}

    name2alloc = dict()
    for alloc in cell_allocs:
        name = '/'.join(alloc['_id'].split('/')[:2])
        if name not in name2alloc:
            name2alloc[name] = {'_id': name,
                                'environment': alloc2env[name],
                                'reservations': []}
        name2alloc[name]['reservations'].append(alloc)

    return name2alloc.values()


class API(object):
    """Treadmill Allocation REST api."""

    def __init__(self):

        def _admin_alloc():
            """Lazily return admin allocation object."""
            return admin.Allocation(context.GLOBAL.ldap.conn)

        def _admin_cell_alloc():
            """Lazily return admin cell allocation object."""
            return admin.CellAllocation(context.GLOBAL.ldap.conn)

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

                @schema.schema({'$ref': 'reservation.json#/resource_id'})
                def get(rsrc_id):
                    """Get reservation configuration."""
                    allocation, cell = rsrc_id.rsplit('/', 1)
                    return _admin_cell_alloc().get([cell, allocation])

                @schema.schema(
                    {'$ref': 'reservation.json#/resource_id'},
                    {'allOf': [{'$ref': 'reservation.json#/resource'},
                               {'$ref': 'reservation.json#/verbs/create'}]}
                )
                def create(rsrc_id, rsrc):
                    """Create reservation."""
                    allocation, cell = rsrc_id.rsplit('/', 1)
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
                    _admin_cell_alloc().update([cell, allocation], rsrc)
                    return _admin_cell_alloc().get([cell, allocation])

                self.get = get
                self.create = create
                self.update = update

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
                               {'$ref': 'assignment.json#/verbs/create'}]}
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
