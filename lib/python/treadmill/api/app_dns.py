"""Implementation of App DNS API"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import copy
import logging

from treadmill import context
from treadmill import schema
from treadmill import utils

_LOGGER = logging.getLogger(__name__)


def _group2dns(app_group):
    """Normalize app group to app_dns"""
    app_dns = copy.deepcopy(app_group)

    if app_dns['group-type'] != 'dns':
        return None

    del app_dns['group-type']

    data = app_dns.get('data')
    del app_dns['data']

    app_dns['alias'] = None
    app_dns['scope'] = None

    if data:
        data_dict = data
        if isinstance(data, list):
            data_dict = utils.equals_list2dict(data)

        if data_dict.get('alias'):
            app_dns['alias'] = data_dict.get('alias')
        if data_dict.get('scope'):
            app_dns['scope'] = data_dict.get('scope')

    return app_dns


def _dns2group(app_dns):
    """Normalize app_dns to app group"""
    app_group = copy.deepcopy(app_dns)
    app_group['group-type'] = 'dns'
    alias = app_group.get('alias')
    scope = app_group.get('scope')
    if not alias:
        return app_group

    app_group['data'] = []
    if alias:
        app_group['data'].append('alias={0}'.format(alias))
    if scope:
        app_group['data'].append('scope={0}'.format(scope))

    del app_group['alias']
    del app_group['scope']
    if not app_group['data']:
        del app_group['data']

    return app_group


class API:
    """Treadmill App DNS REST api."""

    def __init__(self):
        """init"""

        def _admin_app_group():
            """Lazily return admin object."""
            return context.GLOBAL.admin.app_group()

        @schema.schema({'$ref': 'app_dns.json#/resource_id'})
        def get(rsrc_id):
            """Get application configuration."""
            result = _group2dns(_admin_app_group().get(rsrc_id, 'dns'))

            result['_id'] = rsrc_id
            _LOGGER.debug('result: %r', result)

            return result

        @schema.schema(
            {'$ref': 'app_dns.json#/resource_id'},
            {'allOf': [{'$ref': 'app_dns.json#/resource'},
                       {'$ref': 'app_dns.json#/verbs/create'}]}
        )
        def create(rsrc_id, rsrc):
            """Create (configure) application."""
            rsrc = _dns2group(rsrc)
            _LOGGER.debug('rsrc: %r', rsrc)

            _admin_app_group().create(rsrc_id, rsrc)

            result = _group2dns(_admin_app_group().get(rsrc_id, dirty=True))
            _LOGGER.debug('result: %r', result)

            return result

        @schema.schema(
            {'$ref': 'app_dns.json#/resource_id'},
            {'allOf': [{'$ref': 'app_dns.json#/resource'},
                       {'$ref': 'app_dns.json#/verbs/update'}]}
        )
        def update(rsrc_id, rsrc):
            """Update application configuration."""
            rsrc = _dns2group(rsrc)

            _admin_app_group().replace(rsrc_id, rsrc)

            result = _group2dns(_admin_app_group().get(rsrc_id, dirty=True))
            _LOGGER.debug('result: %r', result)

            return result

        @schema.schema({'$ref': 'app_dns.json#/resource_id'})
        def delete(rsrc_id):
            """Delete configured application."""
            _admin_app_group().delete(rsrc_id)

        def _list():
            """List configured applications."""
            app_groups = _admin_app_group().list({'group-type': 'dns'})
            _LOGGER.debug('app_groups: %r', app_groups)

            app_dns_entry = [_group2dns(app_group)
                             for app_group in app_groups]

            return app_dns_entry

        self.get = get
        self.create = create
        self.update = update
        self.delete = delete
        self.list = _list
