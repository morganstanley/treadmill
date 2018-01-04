"""Implementation of lbendpoint API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import re

from treadmill import admin
from treadmill import context
from treadmill import exc
from treadmill import schema

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import lbcontrol
from treadmill.ms import lbendpoint
from treadmill.ms import proiddb

_LOGGER = logging.getLogger(__name__)


# TODO: add try/except around the LBC so that if anything
# happens during creation of the pools and virtuals, we can roll
# back and remove them/clean up
def _setup_virtuals(lbc, rsrc, prodstatus):
    """Setup pool and virtuals"""
    environment = 'prod' if prodstatus == 'prod' else 'dev'

    cells = rsrc.get('cells', [])
    port = rsrc.get('port')

    vips, port = lbendpoint.available_virtual_port(lbc, environment, port=port)
    _LOGGER.debug('vips: %r, port: %r', vips, port)

    rsrc['virtuals'] = []
    for vip in vips:
        vip0 = vip
        if not vip0.endswith('.0'):
            vip0 = '{0}.0'.format(vip)

        virtual = vip0
        if not virtual.endswith('.{0}'.format(port)):
            virtual = '{0}.{1}'.format(vip0, port)
        rsrc['virtuals'].append(virtual)

        filtered_virtuals = lbendpoint.filter_cell_virtuals([virtual], cells)
        virt = lbc.get_virtual(virtual, raw=True)
        _LOGGER.debug('filtered_virtuals: %r', filtered_virtuals)
        _LOGGER.debug('virt: %r', virt)

        if not virt and virtual in filtered_virtuals:
            lbendpoint.create_lbendpoint_virtual(lbc, vip0, port, prodstatus)

    rsrc['vips'] = vips
    rsrc['port'] = port
    rsrc['environment'] = environment

    return rsrc


class API(object):
    """Treadmill lbendpoint REST api."""

    _DEFAULT_LBENV = 'prod'

    def __init__(self):
        """init"""

        def _admin_app_group():
            """Lazily return admin object."""
            return admin.AppGroup(context.GLOBAL.ldap.conn)

        def _lbc(lbenv=None):
            """Lazily return an LB control object"""
            return lbcontrol.LBControl2(lbenv or self._DEFAULT_LBENV)

        def _get_prodstatus(rsrc_id):
            """Get the lbendpoint prodstatus based on the proid environment.

            Raise an error if the lbendpoint name doesn't contain valid proid.
            """
            proid = rsrc_id.split('.')[0]
            prodstatus = proiddb.environment(proid)
            if not prodstatus:
                raise exc.InvalidInputError(
                    rsrc_id, 'Invalid proid: %s' % proid
                )
            _LOGGER.debug('proid: %s, prodstatus: %s', proid, prodstatus)
            return prodstatus

        def _get(rsrc_id, lbc):
            result = lbendpoint.group2lbendpoint(
                _admin_app_group().get(rsrc_id, 'lbendpoint')
            )

            result['environment'] = None
            filtered_virtuals = lbendpoint.filter_cell_virtuals(
                result.get('virtuals', []), result.get('cells', [])
            )
            filtered_virtuals = [
                v for v in filtered_virtuals if not v.endswith('.0')
            ]
            if filtered_virtuals:
                _LOGGER.info('Getting virtual %s', filtered_virtuals[0])
                virtual = lbendpoint.get_lbendpoint_virtual(
                    lbc, filtered_virtuals[0]
                )
                if virtual:
                    result['environment'] = virtual['prodstatus']
                    result['options'] = virtual['options']
                else:
                    _LOGGER.warning('Virtual %s doesn\'t exist',
                                    filtered_virtuals[0])
            return result

        @schema.schema(
            {'$ref': 'lbendpoint.json#/resource_id'},
            lbenv={'$ref': 'lbendpoint.json#/lbenv'})
        def get(rsrc_id, lbenv=None):
            """Get lbendpoint configuration."""
            _LOGGER.info('Getting lbendpoint %s, lbenv: %s', rsrc_id, lbenv)

            lbc = _lbc(lbenv)

            result = _get(rsrc_id, lbc)
            result['_id'] = rsrc_id
            _LOGGER.debug('result: %r', result)

            return result

        @schema.schema(
            {'$ref': 'lbendpoint.json#/resource_id'},
            {'allOf': [{'$ref': 'lbendpoint.json#/resource'},
                       {'$ref': 'lbendpoint.json#/verbs/create'}]},
            lbenv={'$ref': 'lbendpoint.json#/lbenv'}
        )
        def create(rsrc_id, rsrc, lbenv=None):
            """Create (configure) lbendpoint."""
            _LOGGER.info('Creating lbendpoint %s: %r, lbenv: %s',
                         rsrc_id, rsrc, lbenv)

            lbc = _lbc(lbenv)

            prodstatus = _get_prodstatus(rsrc_id)

            rsrc = _setup_virtuals(lbc, rsrc, prodstatus)

            lbendpoint.push_cell_virtuals(
                lbc, rsrc['virtuals'], rsrc.get('cells', [])
            )

            group = lbendpoint.lbendpoint2group(rsrc)
            _LOGGER.debug('group: %r', group)

            _admin_app_group().create(rsrc_id, group)

            result = _get(rsrc_id, lbc)
            _LOGGER.debug('result: %r', result)

            return result

        @schema.schema(
            {'$ref': 'lbendpoint.json#/resource_id'},
            {'allOf': [{'$ref': 'lbendpoint.json#/resource'},
                       {'$ref': 'lbendpoint.json#/options'}]},
            lbenv={'$ref': 'lbendpoint.json#/lbenv'}
        )
        def update(rsrc_id, rsrc, lbenv=None):
            """Update lbendpoint configuration."""
            _LOGGER.info('Updating lbendpoint %s: %r, lbenv: %s',
                         rsrc_id, rsrc, lbenv)

            lbc = _lbc(lbenv)

            prodstatus = _get_prodstatus(rsrc_id)

            lbe = lbendpoint.group2lbendpoint(
                _admin_app_group().get(rsrc_id, 'lbendpoint')
            )
            _LOGGER.debug('lbe: %r', lbe)
            lbe.update(rsrc)
            _LOGGER.debug('lbe (updated): %r', lbe)

            virtuals = lbe.get('virtuals')
            if not virtuals:
                lbe = _setup_virtuals(lbc, lbe, prodstatus)

            port = lbe['port']
            cells = lbe.get('cells', [])
            filtered_virtuals = lbendpoint.filter_cell_virtuals(
                virtuals, cells
            )
            _LOGGER.debug('filtered_virtuals: %r', filtered_virtuals)

            for virtual in filtered_virtuals:
                if virtual.endswith('.0'):
                    continue

                virt = lbc.get_virtual(virtual, raw=True)
                _LOGGER.debug('virt: %r', virt)

                if not virt:
                    vip0 = re.sub(r'\.0\.\d+$', '.0', virtual)
                    lbendpoint.create_lbendpoint_virtual(
                        lbc, vip0, port, prodstatus
                    )
                else:
                    _LOGGER.debug('Updating virtual: %r', virtual)
                    lbendpoint.update_lbendpoint_virtual(
                        lbc, virtual, lbe.get('options', {})
                    )

            lbendpoint.push_cell_virtuals(lbc, virtuals, cells)

            group = lbendpoint.lbendpoint2group(lbe)
            _LOGGER.debug('group: %r', group)

            _admin_app_group().replace(rsrc_id, group)

            result = _get(rsrc_id, lbc)
            _LOGGER.debug('result: %r', result)

            return result

        @schema.schema(
            {'$ref': 'lbendpoint.json#/resource_id'},
            lbenv={'$ref': 'lbendpoint.json#/lbenv'}
        )
        def delete(rsrc_id, lbenv=None):
            """Delete configured lbendpoint."""
            _LOGGER.info('Deleting lbendpoint %s, lbenv: %s', rsrc_id, lbenv)

            lbe = lbendpoint.group2lbendpoint(
                _admin_app_group().get(rsrc_id, 'lbendpoint')
            )
            _LOGGER.debug('lbe: %r', lbe)

            lbc = _lbc(lbenv)
            for virtual in lbe.get('virtuals', []):
                _LOGGER.info('Deleting virtual %s', virtual)
                lbendpoint.delete_lbendpoint_virtual(lbc, virtual)

            _admin_app_group().delete(rsrc_id)

        def _list():
            """List configured applications."""
            app_groups = _admin_app_group().list({'group-type': 'lbendpoint'})
            _LOGGER.debug('app_groups: %r', app_groups)

            lbendpoints = [lbendpoint.group2lbendpoint(app_group)
                           for app_group in app_groups]

            return lbendpoints

        self.get = get
        self.create = create
        self.update = update
        self.delete = delete
        self.list = _list
