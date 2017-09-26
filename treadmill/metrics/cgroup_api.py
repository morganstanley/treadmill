"""Implementation of cgroup metric API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import flask_restplus as restplus

from treadmill.metrics import engine
from treadmill import webutils  # pylint: disable=E0611


_ENGINE = {}


def init(api, cors, **kwargs):
    """Init cgroup API"""
    app_root = os.environ['TREADMILL_APPROOT']

    # default interval is 60
    interval = kwargs['interval']

    _ENGINE['cgroup'] = engine.CgroupReader(app_root, interval)

    namespace = api.namespace(
        'cgroup',
        description='Cgroup fetching REST API'
    )

    @namespace.route('/')
    class _CgroupList(restplus.Resource):
        """Treadmill cgroup API"""

        @webutils.get_api(
            api, cors, marshal=api.marshal_list_with,
        )
        def get(self):
            """Get all cgroups in the list"""
            # get all cgroups values
            return _ENGINE['cgroup'].list()

    @namespace.route('/_bulk')
    class _CgroupBulk(restplus.Resource):
        """Treadmill cgroup bulk API"""

        @webutils.get_api(
            api, cors, marshal=api.marshal_with,
        )
        def get(self):
            """Get the whole cgroups values"""
            return _ENGINE['cgroup'].snapshot()

    @namespace.route('/<cgroup>')
    @api.doc(params={'cgroup': 'Cgroup name'})
    class _CgroupResource(restplus.Resource):
        """Treadmill cgroup resource API"""

        @webutils.get_api(
            api, cors, marshal=api.marshal_with,
        )
        def get(self, cgroup):
            """Get cgroups values."""
            return _ENGINE['cgroup'].get(cgroup)

    return 'cgroup'
