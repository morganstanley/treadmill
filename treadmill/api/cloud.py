from treadmill import authz
import subprocess
import yaml
import os
import json


class API(object):
    """Treadmill Cloud REST API."""

    def __init__(self):

        def configure(args):
            role = args.pop('role').lower()
            domain = args.pop('domain')
            default_mandatory_params = [
                'role',
                'vpc_name',
                'domain',
                'key',
                'image',
                'name',
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

                    _manifest_file = role + '.yml'
                    _file_path = os.path.join('/tmp/', _manifest_file)
                    with open(_file_path, 'w') as f:
                        yaml.dump(_content, f, default_flow_style=False)

                    subprocess.check_output([
                        'treadmill',
                        'admin',
                        'cloud',
                        '--domain',
                        domain,
                        'configure',
                        role,
                        '-m',
                        _file_path
                    ])
                else:
                    raise ValueError(
                        ', '.join(default_mandatory_params) +
                        ' are mandatory arguments for ' + role + ' role .'
                    )

            _mandatory_params = []

            if role == 'node':
                _mandatory_params = [
                    'subnet_id',
                    'ldap_hostname'
                ]
            elif role == 'ldap':
                _mandatory_params = [
                    'cell_subnet_id',
                ]
            elif role == 'cell':
                _params['without_ldap'] = True

            _instantiate(_mandatory_params)

        def delete_servers(args):
            role = args.pop('role').lower()
            default_mandatory_params = [
                'role',
                'vpc_name',
                'domain',
            ]

            _params = dict(filter(
                lambda item: item[1] is not None, args.items()
            ))

            def _validate_mandatory_params(_args):
                _mandatory_args = dict(
                    filter(
                        lambda item: item[0] in _args,
                        args.items()
                    )
                )
                return None not in _mandatory_args.values()

            def _node_params_exists():
                _keys = _params.keys()
                return ('instance_id' in _keys) or ('name' in _keys)

            _mandatory_params = default_mandatory_params
            default_command = [
                'treadmill',
                'admin',
                'cloud',
                '--domain',
                _params['domain'],
                'delete',
                role,
                '--vpc-name',
                _params['vpc_name'],
            ]
            if role == 'node':
                if _node_params_exists():
                    default_command += [
                        '--instance-id',
                        _params['instance_id'],
                        '--name',
                        _params['name']
                    ]
                else:
                    raise ValueError(
                        'Either instance_id or name is required.'
                    )
            elif role == 'ldap':
                _mandatory_params += ['subnet_id']
                default_command += [
                    '--subnet-id',
                    _params['subnet_id'],
                    '--name',
                    _params['name']
                ]
            elif role == 'cell':
                _mandatory_params += ['subnet_id']
                default_command += [
                    '--subnet-id',
                    _params['subnet_id']
                ]

            if _validate_mandatory_params(_mandatory_params):
                subprocess.check_output(default_command)
            else:
                raise ValueError(
                    ', '.join(_mandatory_params) +
                    ' are mandatory arguments for ' + role + ' role.'
                )

        def cells(domain, vpc_name, cell_id):
            _default_command = [
                'treadmill',
                'admin',
                'cloud',
                '--domain',
                domain,
                'list',
                'cell',
            ]

            if cell_id:
                _default_command += [
                    '--subnet-id',
                    cell_id
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
        self.delete_servers = delete_servers
        self.cells = cells
        self.vpcs = vpcs


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
