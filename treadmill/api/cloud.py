from treadmill import authz
import subprocess
import yaml
import os
import json


class API(object):
    """Treadmill Cloud REST API."""

    def __init__(self):

        def configure(
                vpc_name,
                domain,
                name,
                args
        ):
            role = args.pop('role').lower()
            default_mandatory_params = [
                'role',
                'key',
                'image',
                'ipa_admin_password',
            ]

            _params = dict(filter(
                lambda item: item[1] is not None, args.items()
            ))

            def _validate_mandatory_params(_params):
                _mandatory_args = dict(filter(
                    lambda item: item[0] in _params, args.items()
                ))
                return None not in _mandatory_args.values()

            def _instantiate(_mandatory_params_for_role):
                if _validate_mandatory_params(
                    default_mandatory_params + _mandatory_params_for_role
                ):
                    _content = {}
                    _content[role] = _params
                    _content[role]['vpc_name'] = vpc_name
                    _content[role]['name'] = _content[role].get(
                        'name', None
                    ) or name

                    _manifest_file = role + '.yml'
                    _file_path = os.path.join('/tmp/', _manifest_file)
                    with open(_file_path, 'w') as f:
                        yaml.dump(_content, f, default_flow_style=False)

                    try:
                        result = subprocess.check_output([
                            'treadmill',
                            'admin',
                            'cloud',
                            '--domain',
                            domain,
                            'configure',
                            role,
                            '-m',
                            _file_path
                        ], stderr=subprocess.STDOUT)
                    except subprocess.CalledProcessError as e:
                        e.message = e.output.decode('utf-8')
                        raise

                    return json.loads(result.decode('utf-8').replace("'", '"'))
                else:
                    raise ValueError(
                        ', '.join(default_mandatory_params) +
                        ' are mandatory arguments for ' + role + ' role .'
                    )

            _mandatory_params = []

            if role in ['node', 'ldap']:
                _mandatory_params = [
                    'subnet_name',
                ]

            return _instantiate(_mandatory_params)

        def delete_server(
                vpc_name,
                domain,
                name
        ):
            return subprocess.check_output([
                'treadmill',
                'admin',
                'cloud',
                '--domain',
                domain,
                'delete',
                'node',
                '--vpc-name',
                vpc_name,
                '--name',
                name
            ])

        def delete_ldap(
                vpc_name,
                domain,
                name
        ):
            try:
                return subprocess.check_output([
                    'treadmill',
                    'admin',
                    'cloud',
                    '--domain',
                    domain,
                    'delete',
                    'ldap',
                    '--vpc-name',
                    vpc_name,
                    '--name',
                    name
                ], stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                e.message = e.output.decode().replace('\n', '')
                raise

        def delete_cell(
                vpc_name,
                domain,
                cell_name
        ):
            try:
                return subprocess.check_output([
                    'treadmill',
                    'admin',
                    'cloud',
                    '--domain',
                    domain,
                    'delete',
                    'cell',
                    '--vpc-name',
                    vpc_name,
                    '--subnet-name',
                    cell_name
                ], stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                e.message = e.output.decode().replace('\n', '')
                raise

        def cells(domain, vpc_name, cell_name):
            _default_command = [
                'treadmill',
                'admin',
                'cloud',
                '--domain',
                domain,
                'list',
                'cell',
            ]

            if cell_name:
                _default_command += [
                    '--subnet-name',
                    cell_name
                ]
            if vpc_name:
                _default_command += [
                    '--vpc-name',
                    vpc_name,
                ]
            result = subprocess.check_output(_default_command)
            return json.loads(result.decode('utf-8').replace("'", '"'))

        def vpcs(domain, vpc_name):
            _default_command = [
                'treadmill',
                'admin',
                'cloud',
                '--domain',
                domain,
                'list',
                'vpc',
            ]
            if vpc_name:
                _default_command += [
                    '--vpc-name',
                    vpc_name,
                ]
            result = subprocess.check_output(_default_command)
            return json.loads(result.decode('utf-8').replace("'", '"'))

        self.configure = configure
        self.delete_server = delete_server
        self.delete_ldap = delete_ldap
        self.delete_cell = delete_cell
        self.cells = cells
        self.vpcs = vpcs


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
