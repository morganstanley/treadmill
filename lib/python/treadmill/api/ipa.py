from treadmill import authz
import subprocess
import re


class API(object):
    """Treadmill IPA REST API."""

    def __init__(self):

        def add_host(hostname):
            result = subprocess.check_output([
                'ipa',
                'host-add',
                hostname,
                '--random',
                '--force'
            ])
            password_string = result.decode('utf-8').split('\n')[4]
            return password_string.split('password:')[-1].strip()

        def delete_host(hostname):
            result = subprocess.check_output([
                'ipa',
                'host-del',
                hostname
            ]).decode('utf-8')

            assert 'Deleted host "' + hostname + '"' in result

        def service_add(protocol, service, args):
            domain = args.get('domain')
            hostname = args.get('hostname')
            service = protocol + '/' + service
            _service_with_domain = service + '@' + domain.upper()

            subprocess.check_output([
                'ipa',
                'service-add',
                '--force',
                service
            ])

            result = subprocess.check_output([
                'ipa',
                'service-allow-retrieve-keytab',
                _service_with_domain,
                '--hosts=' + hostname
            ])

            _result = result.decode('utf-8').strip().split('\n')[-2]

            assert 'members added 1' in _result

        def add_user(username):
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

        def delete_user(username):
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

        self.add_host = add_host
        self.delete_host = delete_host
        self.service_add = service_add
        self.add_user = add_user
        self.delete_user = delete_user


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
