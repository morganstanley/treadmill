"""Treadmill Cloud REST api.
"""

import flask
import flask_restplus as restplus
from flask_restplus import fields

# Disable E0611: No 'name' in module
from treadmill import webutils  # pylint: disable=E0611


def handle_api_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return flask.abort(flask.make_response(
                flask.jsonify(message=e.message), 400)
            )
    return wrapper


# Old style classes, no init method.
#
# pylint: disable=W0232
def init(api, cors, impl):
    """Configures REST handlers for cloud resource."""

    namespace = webutils.namespace(
        api, __name__, 'Cloud REST operations'
    )

    server_req_model = {
        'role': fields.String(description='Role', required=True),
        'key': fields.String(description='Key', required=True),
        'image': fields.String(description='Image', required=True),
        'ipa_admin_password': fields.String(description='IPA Admin Password',
                                            required=True),
        'subnet_name': fields.String(description='Cell(Subnet) Name',
                                     required=True),
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

    ldap_req_model = {
        'role': fields.String(description='Role', required=True),
        'key': fields.String(description='Key', required=True),
        'image': fields.String(description='Image', required=True),
        'ipa_admin_password': fields.String(description='IPA Admin Password',
                                            required=True),
        'subnet_name': fields.String(description='LDAP Subnet Name',
                                     required=True),
        'region': fields.String(description='Region'),
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

    cell_req_model = {
        'role': fields.String(description='Role', required=True),
        'key': fields.String(description='Key', required=True),
        'image': fields.String(description='Image', required=True),
        'subnet_name': fields.String(description='Cell(Subnet) Name',
                                     required=True),
        'ipa_admin_password': fields.String(description='IPA Admin Password',
                                            required=True),
        'region': fields.String(description='Region'),
        'instance_type': fields.String(description='Instance Type'),
        'tm_release': fields.String(
            description='Treadmill Release URL/Version'
        ),
        'app_root': fields.String(description='Server APP Root'),
        'cidr_block': fields.String(description='Cell CIDR Block'),
    }

    cell_model = api.model(
        'cell', cell_req_model
    )

    @namespace.route(
        '/vpc/<vpc_name>/domain/<domain>/server/<name>'
    )
    @api.doc(params={
        'vpc_name': 'VPC Name',
        'domain': 'Domain',
        'name': 'Node Instance Name Tag'
    })
    class _Server(restplus.Resource):
        """Treadmill Node Server"""
        @webutils.post_api(
            api,
            cors,
            req_model=server_model
        )
        @handle_api_error
        def post(self, vpc_name, domain, name):
            "Configure Worker Node"""
            return impl.configure(
                vpc_name, domain, name, flask.request.json
            )

        @webutils.delete_api(
            api,
            cors,
        )
        @handle_api_error
        def delete(self, vpc_name, domain, name):
            "Delete Worker Node"""
            return impl.delete_server(
                vpc_name, domain, name
            )

    @namespace.route(
        '/vpc/<vpc_name>/domain/<domain>/ldap/<name>'
    )
    @api.doc(params={
        'vpc_name': 'VPC Name',
        'domain': 'Domain',
        'name': 'LDAP Instance Name Tag'
    })
    class _LDAP(restplus.Resource):
        """Treadmill LDAP Server"""
        @webutils.post_api(
            api,
            cors,
            req_model=ldap_model
        )
        @handle_api_error
        def post(self, vpc_name, domain, name):
            """Configure LDAP Server"""
            return impl.configure(
                vpc_name, domain, name, flask.request.json
            )

        @webutils.delete_api(
            api,
            cors,
        )
        @handle_api_error
        def delete(self, vpc_name, domain, name):
            """Delete LDAP Server"""
            return impl.delete_ldap(
                vpc_name, domain, name
            )

    cell_req_parser = api.parser()
    cell_req_parser.add_argument('cell_name', help='CELL(Subnet) Name',
                                 location='args', required=False)

    @namespace.route(
        '/vpc/<vpc_name>/domain/<domain>/cell'
    )
    @api.doc(params={
        'vpc_name': 'VPC Name',
        'domain': 'Domain'
    })
    class _CellConfigure(restplus.Resource):
        """Treadmill CELL Configure"""
        @webutils.get_api(
            api,
            cors,
            parser=cell_req_parser
        )
        def get(self, vpc_name, domain):
            """CELL Info"""
            args = cell_req_parser.parse_args()
            cell_name = args.get('cell_name')
            return impl.cells(domain,
                              vpc_name,
                              cell_name)

        @webutils.post_api(
            api,
            cors,
            req_model=cell_model
        )
        @handle_api_error
        def post(self, vpc_name, domain):
            """Configure Treadmill CELL"""
            return impl.configure(
                vpc_name,
                domain,
                None,
                flask.request.json
            )

    @namespace.route(
        '/vpc/<vpc_name>/domain/<domain>/cell/<cell_name>'
    )
    @api.doc(params={
        'vpc_name': 'VPC Name',
        'domain': 'Domain',
        'cell_name': 'Cell(Subnet) Name'
    })
    class _CellCleaner(restplus.Resource):
        """Treadmill CELL Delete"""
        @handle_api_error
        @webutils.delete_api(
            api,
            cors,
        )
        def delete(self, vpc_name, domain, cell_name):
            """Delete Treadmill CELL"""
            return impl.delete_cell(
                vpc_name,
                domain,
                cell_name
            )

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
            """VPC Info"""
            args = vpc_req_parser.parse_args()
            return impl.vpcs(args.get('domain', ''),
                             args.get('vpc_name', ''))
