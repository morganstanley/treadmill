"""
Treadmill Instance REST api.
"""


import http.client

import flask
import flask_restplus as restplus
from flask_restplus import fields

# Disable E0611: No 'name' in module
from treadmill import webutils  # pylint: disable=E0611
from treadmill.api.model import app as app_model
from treadmill.api.model import error as error_model


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

    count_parser = api.parser()
    count_parser.add_argument('count', type=int, default=1, location='args')

    instances_resp_model = api.model('InstanceResp', {
        'instances': fields.List(fields.String(description='Instances')),
    })

    inst_prio = api.model('InstancePriority', {
        '_id': fields.String(description='Application ID'),
        'priority': fields.Integer(description='Priority'),
    })
    bulk_update_inst_req = api.model('BulkUpdateInstanceReq', {
        'instances': fields.List(fields.Nested(inst_prio)),
    })

    bulk_del_inst_req = api.model('BulkDeleteInstanceReq', {
        'instances': fields.List(fields.String(description='Application ID')),
    })

    # Responses
    app_request_model, app_response_model = app_model.models(api)
    _erorr_id_why, error_model_resp = error_model.models(api)

    bulk_update_resp = api.clone(
        'ApplicationWithError', app_response_model, error_model_resp)

    update_resp = api.model('UpdateInstanceResp', {
        'instances': fields.List(fields.Nested(bulk_update_resp)),
    })

    prio_request_model = api.model('InstancePriorityReq', {
        'priority': fields.List(fields.Integer(description='Priority')),
    })

    @namespace.route(
        '/',
    )
    class _InstanceList(restplus.Resource):
        """Treadmill Instance resource"""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_list_with,
                          resp_model=instances_resp_model)
        def get(self):
            """Returns list of configured applications."""
            return dict(instances=impl.list())

    @namespace.route(
        '/_bulk/delete',
    )
    class _InstanceBulkDelete(restplus.Resource):
        """Treadmill Instance resource"""

        @webutils.post_api(api, cors,
                           req_model=bulk_del_inst_req,)
        def post(self):
            """Bulk deletes list of instances."""
            instance_ids = flask.request.json['instances']
            for instance_id in instance_ids:
                impl.delete(instance_id)

    @namespace.route(
        '/_bulk/update',
    )
    class _InstanceBulkUpdate(restplus.Resource):
        """Treadmill Instance resource"""

        @webutils.post_api(api, cors,
                           req_model=bulk_update_inst_req,
                           resp_model=update_resp)
        def post(self):
            """Bulk updates list of instances."""
            deltas = flask.request.json['instances']
            if not isinstance(deltas, list):
                api.abort(http.client.BAD_REQUEST, 'Not a list: %r.' % deltas)
            result = []
            for delta in deltas:
                if not isinstance(delta, dict):
                    api.abort(http.client.BAD_REQUEST,
                              'Not a dict: %r.' % delta)
                if '_id' not in delta:
                    api.abort(http.client.BAD_REQUEST,
                              'Missing _id attribute: %r' % delta)

                # rest of validation is done in API.
                rsrc_id = delta.get('_id')
                del delta['_id']
                try:
                    result.append(impl.update(rsrc_id, delta))
                except Exception as err:  # pylint: disable=W0703
                    result.append({'_error': {'_id': rsrc_id,
                                              'why': str(err)}})
            return {'instances': result}

    @namespace.route('/<instance_id>')
    @api.doc(params={'instance_id': 'Instance ID/name'})
    class _InstanceResource(restplus.Resource):
        """Treadmill Instance resource."""

        @webutils.get_api(api, cors,
                          marshal=api.marshal_with,
                          resp_model=app_response_model)
        def get(self, instance_id):
            """Return Treadmill instance configuration."""
            instance = impl.get(instance_id)
            if not instance:
                api.abort(http.client.NOT_FOUND,
                          'Instance does not exist: %s' % instance_id)
            return instance

        @webutils.post_api(api, cors,
                           req_model=app_request_model,
                           resp_model=instances_resp_model,
                           parser=count_parser)
        def post(self, instance_id):
            """Creates Treadmill instance."""
            args = count_parser.parse_args()
            count = args.get('count', 1)

            instances = impl.create(instance_id, flask.request.json, count)
            return {'instances': instances}

        @webutils.put_api(api, cors,
                          req_model=prio_request_model,)
        def put(self, instance_id):
            """Updates Treadmill instance configuration."""
            return impl.update(instance_id, flask.request.json)

        @webutils.delete_api(api, cors)
        def delete(self, instance_id):
            """Deletes Treadmill application."""
            return impl.delete(instance_id)
