"""
Treadmill Instance REST api.
"""
from __future__ import absolute_import

import httplib

# For some reason pylint complains about restplus not being able to import.
#
# pylint: disable=E0611,F0401
import flask
import flask.ext.restplus as restplus
from flask_restful import reqparse

from treadmill import webutils


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for instance resource."""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912
    namespace = webutils.namespace(
        api, __name__, 'Instance REST operations'
    )

    @namespace.route(
        '/',
    )
    class _InstanceList(restplus.Resource):
        """Treadmill Instance resource"""

        @webutils.get_api(api, cors)
        def get(self):
            """Returns list of configured applications."""
            return impl.list()

    @namespace.route(
        '/_bulk/delete',
    )
    class _InstanceBulkDelete(restplus.Resource):
        """Treadmill Instance resource"""

        @webutils.post_api(api, cors)
        def post(self):
            """Bulk deletes list of instances."""
            instance_ids = flask.request.json
            for instance_id in instance_ids:
                impl.delete(instance_id)

    @namespace.route(
        '/_bulk/update',
    )
    class _InstanceBulkUpdate(restplus.Resource):
        """Treadmill Instance resource"""

        @webutils.post_api(api, cors)
        def post(self):
            """Bulk updates list of instances."""
            deltas = flask.request.json
            if not isinstance(deltas, list):
                api.abort(httplib.BAD_REQUEST, 'Not a list: %r.', deltas)
            result = []
            for delta in deltas:
                if not isinstance(delta, dict):
                    api.abort(httplib.BAD_REQUEST, 'Not a dict: %r.' % delta)
                if '_id' not in delta:
                    api.abort(httplib.BAD_REQUEST,
                              'Missing _id attribute: %r' % delta)

                # rest of validation is done in API.
                rsrc_id = delta.get('_id')
                del delta['_id']
                try:
                    result.append(impl.update(rsrc_id, delta))
                except Exception as err:  # pylint: disable=W0703
                    result.append({'_error': {'_id': rsrc_id,
                                              'why': str(err)}})
            return result

    @namespace.route('/<instance_id>')
    class _InstanceResource(restplus.Resource):
        """Treadmill Instance resource."""

        @webutils.get_api(api, cors)
        def get(self, instance_id):
            """Return Treadmill instance configuration."""
            instance = impl.get(instance_id)
            if not instance:
                api.abort(httplib.NOT_FOUND,
                          'Instance does not exist: %s' % instance_id)
            return instance

        @webutils.delete_api(api, cors)
        def delete(self, instance_id):
            """Deletes Treadmill application."""
            return impl.delete(instance_id)

        @webutils.put_api(api, cors)
        def put(self, instance_id):
            """Updates Treadmill instance configuration."""
            return impl.update(instance_id, flask.request.json)

        @webutils.post_api(api, cors)
        def post(self, instance_id):
            """Creates Treadmill instance."""
            parser = reqparse.RequestParser()
            parser.add_argument('count', type=int, default=1)
            args = parser.parse_args()
            count = args.get('count', 1)

            return impl.create(instance_id, flask.request.json, count)
