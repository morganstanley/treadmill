"""Implementation of cgroup metric API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import flask_restplus as restplus

from treadmill import exc
from treadmill import webutils

_LOGGER = logging.getLogger(__name__)


def init(api, cors, impl):
    """Configures REST handlers for cgroup resource."""

    namespace = api.namespace(
        'cgroup',
        description='Cgroup fetching REST API',
    )

    detail_parser = api.parser()
    detail_parser.add_argument(
        'detail',
        help='Flag to control of returning cgroup details',
        location='args',
        required=False,
        default=False,
        type=restplus.inputs.boolean,
    )

    def _check_resource(cgroup, data):
        """Validate cgroup stats resource."""
        if not data:
            raise exc.NotFoundError(
                'Cgroup does not exist: {}'.format(cgroup)
            )

    @namespace.route('/system')
    class _SystemSlice(restplus.Resource):
        """system.slice cgroup resource"""

        @webutils.get_api(api, cors, marshal=api.marshal_with)
        def get(self):
            """Get system.slice cgroup resource"""
            name = 'system.slice'
            data = impl.system(name)
            _check_resource(name, data)
            return data

    @namespace.route('/treadmill')
    class _Treadmill(restplus.Resource):
        """Treadmill top level cgroup resource"""

        @webutils.get_api(api, cors, marshal=api.marshal_with)
        def get(self):
            """Get Treadmill top level cgroup resource"""
            name = 'treadmill'
            data = impl.system(name)
            _check_resource(name, data)
            return data

    @namespace.route('/treadmill/*/')
    class _TreadmillAll(restplus.Resource):
        """All Treadmill core/apps cgroup resources"""

        @webutils.get_api(api, cors, marshal=api.marshal_with)
        def get(self):
            """Get All Treadmill core/apps cgroup resources"""
            return {
                'core': impl.system('treadmill', 'core'),
                'apps': impl.system('treadmill', 'apps'),
            }

    @namespace.route('/treadmill/core')
    class _TreadmillCore(restplus.Resource):
        """Treadmill aggregated core service cgroup resource"""

        @webutils.get_api(api, cors, marshal=api.marshal_with)
        def get(self):
            """Get Treadmill aggregated core service cgroup resource"""
            data = impl.system('treadmill', 'core')
            _check_resource('treadmill.core', data)
            return data

    @namespace.route('/treadmill/core/<name>')
    class _TreadmillCoreService(restplus.Resource):
        """Treadmill core service cgroup resource"""

        @webutils.get_api(api, cors, marshal=api.marshal_with)
        def get(self, name):
            """Get Treadmill core service cgroup resource"""
            data = impl.service(name)
            _check_resource('core.{0}'.format(name), data)
            return data

    @namespace.route('/treadmill/core/*/')
    class _TreadmillCoreServiceAll(restplus.Resource):
        """All Treadmill core service cgroup resources"""

        @webutils.get_api(
            api, cors, marshal=api.marshal_with, parser=detail_parser
        )
        def get(self):
            """Get all Treadmill core service cgroup resources"""
            args = detail_parser.parse_args()
            return impl.services(detail=args.get('detail'))

    @namespace.route('/treadmill/apps')
    class _TreadmillApps(restplus.Resource):
        """Treadmill aggregated app cgroup resource"""

        @webutils.get_api(api, cors, marshal=api.marshal_with)
        def get(self):
            """Get Treadmill aggregated app cgroup resource"""
            data = impl.system('treadmill', 'apps')
            _check_resource('treadmill.apps', data)
            return data

    @namespace.route('/treadmill/apps/<name>')
    class _TreadmillApp(restplus.Resource):
        """Treadmill app cgroup resource"""

        @webutils.get_api(api, cors, marshal=api.marshal_with)
        def get(self, name):
            """Get Treadmill app cgroup resource"""
            data = impl.app(name)
            _check_resource('apps.{0}'.format(name), data)
            return data

    @namespace.route('/treadmill/apps/*/')
    class _TreadmillAppsAll(restplus.Resource):
        """All Treadmill app cgroup resources"""

        @webutils.get_api(
            api, cors, marshal=api.marshal_with, parser=detail_parser
        )
        def get(self):
            """Get all Treadmill app cgroup resources"""
            args = detail_parser.parse_args()
            return impl.apps(detail=args.get('detail'))
