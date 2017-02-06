"""Implementation of instance API."""


import importlib
import logging

from treadmill import admin
from treadmill import authz
from treadmill import context
from treadmill import exc
from treadmill import master
from treadmill import schema

from treadmill.api import app


_LOGGER = logging.getLogger(__name__)


@schema.schema(
    {'allOf': [{'$ref': 'instance.json#/resource'},
               {'$ref': 'instance.json#/verbs/schedule'}]},
)
def _validate(_rsrc):
    """Validate instance manifest."""
    pass


class API(object):
    """Treadmill Instance REST api."""

    def __init__(self):

        instance_plugin = None
        try:
            instance_plugin = importlib.import_module(
                'treadmill.plugins.api.instance')
        except ImportError as err:
            _LOGGER.info('Unable to load auth plugin: %s', err)

        def _list():
            """List configured instances."""
            return master.list_scheduled_apps(
                context.GLOBAL.zk.conn
            )

        @schema.schema({'$ref': 'instance.json#/resource_id'})
        def get(rsrc_id):
            """Get instance configuration."""
            inst = master.get_app(context.GLOBAL.zk.conn, rsrc_id)
            if inst is None:
                return inst

            inst['_id'] = rsrc_id
            if instance_plugin:
                return instance_plugin.remove_attributes(inst)
            else:
                return inst

        @schema.schema(
            {'$ref': 'app.json#/resource_id'},
            {'allOf': [{'$ref': 'instance.json#/resource'},
                       {'$ref': 'instance.json#/verbs/create'}]},
            count={'type': 'integer', 'minimum': 1, 'maximum': 1000}
        )
        def create(rsrc_id, rsrc, count=1):
            """Create (configure) instance."""
            _LOGGER.info('create: count = %s, %s %r', count, rsrc_id, rsrc)

            admin_app = admin.Application(context.GLOBAL.ldap.conn)
            if not rsrc:
                configured = admin_app.get(rsrc_id)
                _LOGGER.info('Configured: %s %r', rsrc_id, configured)
            else:
                # Make sure defaults are present
                configured = admin_app.from_entry(admin_app.to_entry(rsrc))
                app.verify_feature(rsrc.get('features', []))

            if '_id' in configured:
                del configured['_id']

            _validate(configured)

            if instance_plugin:
                configured = instance_plugin.add_attributes(rsrc_id,
                                                            configured)

            if 'proid' not in configured:
                raise exc.TreadmillError(
                    'Missing required attribute: proid')
            if 'environment' not in configured:
                raise exc.TreadmillError(
                    'Missing required attribute: environment')

            if 'identity_group' not in configured:
                configured['identity_group'] = None

            if 'affinity' not in configured:
                configured['affinity'] = '{0}.{1}'.format(*rsrc_id.split('.'))

            scheduled = master.create_apps(context.GLOBAL.zk.conn,
                                           rsrc_id, configured, count)
            return scheduled

        @schema.schema(
            {'$ref': 'instance.json#/resource_id'},
            {'allOf': [{'$ref': 'instance.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update instance configuration."""
            _LOGGER.info('update: %s %r', rsrc_id, rsrc)

            delta = {rsrc_id: rsrc['priority']}

            master.update_app_priorities(context.GLOBAL.zk.conn, delta)
            return master.get_app(context.GLOBAL.zk.conn, rsrc_id)

        @schema.schema({'$ref': 'instance.json#/resource_id'})
        def delete(rsrc_id):
            """Delete configured instance."""
            _LOGGER.info('delete: %s', rsrc_id)

            master.delete_apps(context.GLOBAL.zk.conn, [rsrc_id])

        self.list = _list
        self.get = get
        self.create = create
        self.update = update
        self.delete = delete


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
