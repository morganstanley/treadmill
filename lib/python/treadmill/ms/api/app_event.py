"""Implementation of App Event API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import copy
import logging

from treadmill import context
from treadmill import schema
from treadmill import admin
from treadmill import utils

_LOGGER = logging.getLogger(__name__)


def _group2event(app_group):
    """Normalize app group to app_event"""
    app_event = copy.deepcopy(app_group)

    if app_event['group-type'] != 'event':
        return None

    del app_event['group-type']

    data = app_event.get('data')
    del app_event['data']

    app_event['pending'] = None
    app_event['exit'] = None

    if data:
        data_dict = data
        if isinstance(data, list):
            data_dict = utils.equals_list2dict(data)

        if data_dict.get('pending'):
            # change to int as stored as string in ldap
            app_event['pending'] = int(data_dict.get('pending'))
        if data_dict.get('exit'):
            app_event['exit'] = sorted(data_dict.get('exit').split(','))

    return app_event


def _event2group(app_event):
    """Normalize app_event to app group"""
    app_group = copy.deepcopy(app_event)
    app_group['group-type'] = 'event'
    # event do not have endpoint
    app_group['endpoint-name'] = []
    pending = app_group.get('pending')
    exit_type = app_group.get('exit')

    app_group['data'] = []
    if pending:
        # this will make 'pending' stored as str rather than int
        app_group['data'].append('pending={0}'.format(pending))

    if exit_type:
        app_group['data'].append('exit={0}'.format(','.join(exit_type)))

    if 'pending' in app_group:
        del app_group['pending']

    if 'exit' in app_group:
        del app_group['exit']

    if not app_group['data']:
        del app_group['data']

    return app_group


class API(object):
    """Treadmill App DNS REST api."""

    def __init__(self):
        """init"""

        def _admin_app_group():
            """Lazily return admin object."""
            return admin.AppGroup(context.GLOBAL.ldap.conn)

        @schema.schema({'$ref': 'app_event.json#/resource_id'})
        def get(rsrc_id):
            """Get application configuration."""
            result = _group2event(_admin_app_group().get(rsrc_id, 'event'))

            result['_id'] = rsrc_id
            _LOGGER.debug('result: %r', result)

            return result

        @schema.schema(
            {'$ref': 'app_event.json#/resource_id'},
            {'allOf': [{'$ref': 'app_event.json#/resource'},
                       {'$ref': 'app_event.json#/verbs/create'}]}
        )
        def create(rsrc_id, rsrc):
            """Create (configure) application."""
            rsrc = _event2group(rsrc)
            _LOGGER.debug('creating rsrc: %r', rsrc)

            _admin_app_group().create(rsrc_id, rsrc)

            result = _group2event(_admin_app_group().get(rsrc_id))
            _LOGGER.debug('result: %r', result)

            return result

        @schema.schema(
            {'$ref': 'app_event.json#/resource_id'},
            {'allOf': [{'$ref': 'app_event.json#/resource'},
                       {'$ref': 'app_event.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update application configuration."""
            result = _group2event(_admin_app_group().get(rsrc_id, 'event'))
            result.update(rsrc)
            rsrc = _event2group(result)
            _LOGGER.debug('updating rsrc: %r', rsrc)

            _admin_app_group().replace(rsrc_id, rsrc)

            result = _group2event(_admin_app_group().get(rsrc_id))
            _LOGGER.debug('result: %r', result)

            return result

        @schema.schema({'$ref': 'app_event.json#/resource_id'})
        def delete(rsrc_id):
            """Delete configured application."""
            _admin_app_group().delete(rsrc_id)
            return None

        def _list():
            """List configured applications."""
            app_groups = _admin_app_group().list({'group-type': 'event'})
            _LOGGER.debug('app_groups: %r', app_groups)

            app_event_entry = [_group2event(app_group)
                               for app_group in app_groups]

            return app_event_entry

        self.get = get
        self.create = create
        self.update = update
        self.delete = delete
        self.list = _list
