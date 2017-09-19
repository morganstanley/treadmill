"""
Treadmill IPA REST api.
"""

import flask
import flask_restplus as restplus
from flask_restplus import fields

# Disable E0611: No 'name' in module
from treadmill import webutils  # pylint: disable=E0611


def handle_api_error(func):
    def wrapper(*args):
        try:
            return func(*args)
        except Exception as e:
            return flask.abort(400, {'message': e.message})
    return wrapper


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for ipa resource."""

    namespace = webutils.namespace(
        api, __name__, 'IPA REST operations'
    )

    service_req_model = {
        'service': fields.String(description='Service Name'),
        'hostname': fields.String(description='Hostname'),
        'domain': fields.String(description='Domain')
    }

    service_model = api.model(
        'service', service_req_model
    )

    server_req_model = {
        'vpc_name': fields.String(description='VPC Name'),
        'domain': fields.String(description='Domain'),
        'role': fields.String(description='Role'),
        'key': fields.String(description='Key'),
        'image': fields.String(description='Image'),
        'name': fields.String(description='Instance Name'),
        'ipa_admin_password': fields.String(description='IPA Admin Password'),
        'subnet_id': fields.String(description='Cell ID'),
        'region': fields.String(description='Region'),
        'with_api': fields.String(description='With API Flag'),
        'instance_type': fields.String(description='Instance Type'),
        'tm_release': fields.String(
            description='Treadmill Release URL/Version'
        ),
        'app_root': fields.String(description='Server APP Root'),
    }

    server_model = api.model(
        'server', server_req_model
    )

    server_del_req_model = {
        'vpc_name': fields.String(description='VPC Name'),
        'domain': fields.String(description='Domain'),
        'role': fields.String(description='Role'),
        'name': fields.String(description='Node Instance Name'),
        'instance_id': fields.String(description='Node Instance ID'),
    }

    server_del_model = api.model(
        'server_del', server_del_req_model
    )

    ldap_req_model = {
        'vpc_name': fields.String(description='VPC Name'),
        'domain': fields.String(description='Domain'),
        'role': fields.String(description='Role'),
        'key': fields.String(description='Key'),
        'image': fields.String(description='Image'),
        'name': fields.String(description='Instance Name'),
        'ipa_admin_password': fields.String(description='IPA Admin Password'),
        'cell_subnet_id': fields.String(description='Cell ID'),
        'region': fields.String(description='Region'),
        'ldap_subnet_id': fields.String(description='LDAP Subnet ID'),
        'ldap_cidr_block': fields.String(description='LDAP CIDR Block'),
        'instance_type': fields.String(description='Instance Type'),
        'tm_release': fields.String(
            description='Treadmill Release URL/Version'
        ),
        'app_root': fields.String(description='Server APP Root'),
    }

    ldap_model = api.model(
        'ldap', ldap_req_model
    )

    ldap_del_req_model = {
        'vpc_name': fields.String(description='VPC Name'),
        'domain': fields.String(description='Domain'),
        'role': fields.String(description='Role'),
        'name': fields.String(description='LDAP Instance Name [OPTIONAL]'),
        'subnet_id': fields.String(description='Subnet ID'),
    }

    ldap_del_model = api.model(
        'ldap_del', ldap_del_req_model
    )

    cell_req_model = {
        'vpc_name': fields.String(description='VPC Name'),
        'domain': fields.String(description='Domain'),
        'role': fields.String(description='Role'),
        'key': fields.String(description='Key'),
        'image': fields.String(description='Image'),
        'region': fields.String(description='Region'),
        'ipa_admin_password': fields.String(description='IPA Admin Password'),
        'instance_type': fields.String(description='Instance Type'),
        'tm_release': fields.String(
            description='Treadmill Release URL/Version'
        ),
        'app_root': fields.String(description='Server APP Root'),
        'cell_cidr_block': fields.String(description='Cell CIDR Block'),
        'subnet_id': fields.String(description='Subnet ID'),
    }

    cell_model = api.model(
        'cell', cell_req_model
    )

    cell_del_req_model = {
        'vpc_name': fields.String(description='VPC Name'),
        'domain': fields.String(description='Domain'),
        'subnet_id': fields.String(description='Subnet(Cell) ID'),
    }

    cell_del_model = api.model(
        'cell_del', cell_del_req_model
    )

    host_req_model = {
        'hostname': fields.String(description='Hostname'),
    }

    host_model = api.model(
        'host', host_req_model
    )

    user_req_model = {
        'username': fields.String(description='Username'),
    }

    user_model = api.model(
        'user', user_req_model
    )

    @namespace.route('/host')
    class _Host(restplus.Resource):
        """Treadmill IPA Host"""

        @webutils.post_api(
            api,
            cors,
            req_model=host_model
        )
        def post(self):
            """Adds host to IPA."""
            return impl.add_host(flask.request.json)

        @webutils.delete_api(
            api,
            cors,
            req_model=host_model
        )
        def delete(self):
            """Deletes host from IPA."""
            return impl.delete_host(flask.request.json)

    @namespace.route('/user')
    class _User(restplus.Resource):
        """Treadmill IPA User"""

        @webutils.post_api(
            api,
            cors,
            req_model=user_model
        )
        @handle_api_error
        def post(self):
            """Adds User to IPA."""
            impl.add_user(flask.request.json)

        @webutils.delete_api(
            api,
            cors,
            req_model=user_model
        )
        @handle_api_error
        def delete(self):
            """Deletes User from IPA."""
            return impl.delete_user(flask.request.json)

    @namespace.route('/service')
    class _Service(restplus.Resource):
        """Treadmill IPA Service"""
        @webutils.post_api(
            api,
            cors,
            req_model=service_model
        )
        def post(self):
            """Add Service to IPA"""
            return impl.service_add(flask.request.json)

    @namespace.route('/server')
    class _Server(restplus.Resource):
        """Treadmill Node Server"""
        @webutils.post_api(
            api,
            cors,
            req_model=server_model
        )
        def post(self):
            "Configure Worker Node"""
            return impl.configure(flask.request.json)

        @webutils.delete_api(
            api,
            cors,
            req_model=server_del_model
        )
        def delete(self):
            "Delete Worker Node"""
            return impl.delete_servers(flask.request.json)

    @namespace.route('/ldap')
    class _LDAP(restplus.Resource):
        """Treadmill LDAP Server"""
        @webutils.post_api(
            api,
            cors,
            req_model=ldap_model
        )
        def post(self):
            """Configure LDAP Server"""
            return impl.configure(flask.request.json)

        @webutils.delete_api(
            api,
            cors,
            req_model=ldap_del_model
        )
        def delete(self):
            """Delete LDAP Server"""
            return impl.delete_servers(flask.request.json)

    vpc_req_parser = api.parser()
    vpc_req_parser.add_argument('vpc_name', help='VPC Name',
                                location='args', required=False)
    vpc_req_parser.add_argument('domain', help='Domain',
                                location='args', required=True)

    @namespace.route('/vpc')
    class _Vpc(restplus.Resource):
        """VPC"""
        @webutils.get_api(
            api,
            cors,
            parser=vpc_req_parser
        )
        def get(self):
            args = vpc_req_parser.parse_args()
            return impl.vpcs(args.get('domain', ''),
                             args.get('vpc_name', ''))

    cell_req_parser = api.parser()
    cell_req_parser.add_argument('cell_id', help='Cell Id',
                                 location='args', required=False)
    cell_req_parser.add_argument('domain', help='Domain',
                                 location='args', required=True)
    cell_req_parser.add_argument('vpc_name', help='VPC Name',
                                 location='args', required=False)

    @namespace.route('/cell')
    class _Cell(restplus.Resource):
        """Treadmill CELL"""

        @webutils.get_api(
            api,
            cors,
            parser=cell_req_parser
        )
        def get(self):
            args = cell_req_parser.parse_args()
            return impl.cells(args.get('domain', ''),
                              args.get('vpc_name', ''),
                              args.get('cell_id', ''))

        @webutils.post_api(
            api,
            cors,
            req_model=cell_model
        )
        def post(self):
            """Configure Treadmill CELL"""
            return impl.configure(flask.request.json)

        @webutils.delete_api(
            api,
            cors,
            req_model=cell_del_model
        )
        def delete(self):
            """Delete Treadmill CELL"""
            return impl.configure(flask.request.json)
