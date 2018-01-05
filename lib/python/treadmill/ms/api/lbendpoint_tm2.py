"""Implementation of lbendpoint-tm2 API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import admin
from treadmill import context
from treadmill import exc
from treadmill import schema

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import lbcontrol
from treadmill.ms import lbendpoint

_LOGGER = logging.getLogger(__name__)


class API(object):
    """Treadmill lbendpoint-tm2 API."""

    _LBENV = 'prod'

    def __init__(self):
        """init"""

        def _admin_app_group():
            """Lazily return admin app group object."""
            return admin.AppGroup(context.GLOBAL.ldap.conn)

        def _admin_cell():
            """Lazily return admin cell object."""
            return admin.Cell(context.GLOBAL.ldap.conn)

        def _lbc():
            """Lazily return LBControl object."""
            return lbcontrol.LBControl2(self._LBENV)

        @schema.schema({'$ref': 'lbendpoint_tm2.json#/resource_id'})
        def get(rsrc_id):
            """Get TM2 lbendpoint."""
            _LOGGER.info('Getting TM2 lbendpoint %s', rsrc_id)

            result = lbendpoint.group2lbendpoint(
                _admin_app_group().get(rsrc_id, 'lbendpoint-tm2')
            )
            _LOGGER.debug('result: %r', result)
            return result

        @schema.schema(
            {'$ref': 'lbendpoint_tm2.json#/resource_id'},
            {'$ref': 'lbendpoint_tm2.json#/resource'}
        )
        def update(rsrc_id, rsrc):
            """Update TM2 lbendpoint."""
            _LOGGER.info('Updating TM2 lbendpoint %s: %r', rsrc_id, rsrc)
            admin_app_group = _admin_app_group()

            lbe = lbendpoint.group2lbendpoint(
                admin_app_group.get(rsrc_id, 'lbendpoint-tm2')
            )
            _LOGGER.debug('lbe: %r', lbe)

            cells = rsrc.get('cells')
            if cells:
                location = lbe['location']
                location_cells = _admin_cell().list({'location': location})
                location_cells = [cell['_id'] for cell in location_cells]
                invalid_cells = set(cells) - set(location_cells)
                if invalid_cells:
                    raise exc.InvalidInputError(
                        rsrc_id,
                        'Invalid cells: %s not in %s' % (
                            ','.join(invalid_cells), location
                        )
                    )

            lbe.update(rsrc)
            _LOGGER.debug('lbe (updated): %r', lbe)

            group = lbendpoint.lbendpoint2group(lbe, 'lbendpoint-tm2')
            _LOGGER.debug('group: %r', group)

            admin_app_group.replace(rsrc_id, group)

            result = lbendpoint.group2lbendpoint(
                admin_app_group.get(rsrc_id, 'lbendpoint-tm2')
            )
            _LOGGER.debug('result: %r', result)
            return result

        @schema.schema({'$ref': 'lbendpoint_tm2.json#/resource_id'})
        def delete(rsrc_id):
            """Delete TM2 lbendpoint and virtual/pool."""
            _LOGGER.info('Deleting TM2 lbendpoint %s', rsrc_id)
            admin_app_group = _admin_app_group()

            lbe = lbendpoint.group2lbendpoint(
                admin_app_group.get(rsrc_id, 'lbendpoint-tm2')
            )
            _LOGGER.debug('lbe: %r', lbe)

            _LOGGER.info('Deleting virtual %s', lbe['virtual'])
            lbendpoint.delete_lbendpoint_virtual(_lbc(), lbe['virtual'])

            admin_app_group.delete(rsrc_id)

        def _list():
            """List TM2 lbendpoints."""
            _LOGGER.info('Listing TM2 lbendpoints')

            groups = _admin_app_group().list({'group-type': 'lbendpoint-tm2'})
            return [
                lbendpoint.group2lbendpoint(group)
                for group in groups
            ]

        self.get = get
        self.update = update
        self.delete = delete
        self.list = _list
