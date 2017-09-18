from treadmill import authz
import subprocess
import re
import yaml
import os


class API(object):
    """Treadmill IPA REST API."""

    def __init__(self):

        def add_host(args):
            hostname = args.get('hostname')
            result = subprocess.check_output([
                'ipa',
                'host-add',
                hostname,
                '--random',
                '--force'
            ])
            password_string = result.decode('utf-8').split('\n')[4]
            return password_string.split('password:')[-1].strip()

        def delete_host(args):
            hostname = args.get('hostname')
            result = subprocess.check_output([
                'ipa',
                'host-del',
                hostname
            ]).decode('utf-8')

            assert 'Deleted host "' + hostname + '"' in result

        def service_add(args):
            domain = args.get('domain')
            hostname = args.get('hostname')
            _service = args.get('service')
            _service_with_domain = _service + '@' + domain.upper()

            subprocess.check_output([
                'ipa',
                'service-add',
                '--force',
                _service
            ])

            result = subprocess.check_output([
                'ipa',
                'service-allow-retrieve-keytab',
                _service_with_domain,
                '--hosts=' + hostname
            ])

            _result = result.decode('utf-8').strip().split('\n')[-2]

            assert 'members added 1' in _result

        def add_user(args):
            username = args.get('username')

            try:
                result = subprocess.check_output([
                    'ipa',
                    '-n',
                    'user-add',
                    '--first=' + username,
                    '--last=proid',
                    '--shell=/bin/bash',
                    '--class=proid',
                    '--random',
                    username
                ])
            except subprocess.CalledProcessError as e:
                e.message = 'Couldn\'t add user, it may already exist.'
                raise

            if result:
                otp = re.search(
                    r'Random password: .*',
                    result.decode('utf-8')
                ).group(0).split(": ")[-1]

                new_pwd = subprocess.check_output([
                    'openssl',
                    'rand',
                    '-base64',
                    '12'
                ])

                kpasswd_proc = subprocess.Popen(
                    [
                        'kpasswd',
                        username
                    ],
                    stdout=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                kpasswd_proc.communicate(
                    input=otp.encode('utf-8') + b'\n' + new_pwd + new_pwd
                )

        def delete_user(args):
            username = args.get('username')

            try:
                result = subprocess.check_output([
                    'ipa',
                    'user-del',
                    username
                ]).decode('utf-8')
            except subprocess.CalledProcessError as e:
                e.message = 'Couldn\'t delete user, it may not exist.'
                raise

            if result:
                assert 'Deleted user "' + username + '"' in result

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
                        'cloud',
                        '--domain',
                        domain,
                        'init',
                        role,
                        '-m',
                        _file_path
                    ])
                else:
                    raise ValueError(
                        ', '.join(default_mandatory_params) +
                        ' are mandatory arguments.'
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

        self.add_host = add_host
        self.delete_host = delete_host
        self.service_add = service_add
        self.add_user = add_user
        self.delete_user = delete_user
        self.configure = configure


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
