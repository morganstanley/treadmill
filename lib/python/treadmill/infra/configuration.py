import pkg_resources
from jinja2 import Environment, FileSystemLoader

from treadmill.infra import SCRIPT_DIR
from treadmill.infra import connection
from treadmill.dist import TREADMILL_BIN


class Configuration:
    """Configure instances"""

    def __init__(self):
        self.setup_scripts = None
        self.subnet_id = None

    def get_userdata(self):
        if not self.setup_scripts:
            return ''

        environment = Environment(loader=FileSystemLoader(
            pkg_resources.resource_filename(__name__, '')
        ))
        userdata = ''
        # Add initializer script
        self.setup_scripts.insert(0, {'name': 'init.sh'})
        for script in self.setup_scripts:
            script['vars'] = script.get('vars', {})
            script['vars']['TREADMILL'] = TREADMILL_BIN
            script['vars']['SUBNET_ID'] = self.subnet_id
            with open(SCRIPT_DIR + script['name'], 'r') as data:
                template = environment.from_string(data.read())
                userdata += template.render(script['vars']) + '\n'
        return userdata


class Master(Configuration):
    def __init__(self, hostname, otp, app_root, ldap_hostname,
                 tm_release, ipa_admin_password, idx,
                 proid, zk_url):
        super().__init__()

        self.setup_scripts = [
            {
                'name': 'provision-base.sh',
                'vars': {
                    'DOMAIN': connection.Connection.context.domain,
                    'SUBNET_ID': self.subnet_id,
                    'APP_ROOT': app_root,
                    'LDAP_HOSTNAME': ldap_hostname,
                    'HOSTNAME': hostname,
                    'PROID': proid,
                    'ZK_URL': zk_url,
                },
            }, {
                'name': 'install-ipa-client-with-otp.sh',
                'vars': {
                    'OTP': otp
                }
            }, {
                'name': 'install-treadmill.sh',
                'vars': {'TREADMILL_RELEASE': tm_release}
            }, {
                'name': 'configure-master.sh',
                'vars': {
                    'SUBNET_ID': self.subnet_id,
                    'APP_ROOT': app_root,
                    'IPA_ADMIN_PASSWORD': ipa_admin_password,
                    'IDX': idx
                },
            },
        ]


class LDAP(Configuration):
    def __init__(self, tm_release, app_root, otp, ipa_admin_password,
                 ipa_server_hostname, hostname, proid):
        super().__init__()

        self.setup_scripts = [
            {
                'name': 'provision-base.sh',
                'vars': {
                    'DOMAIN': connection.Connection.context.domain,
                    'APP_ROOT': app_root,
                    'LDAP_HOSTNAME': hostname,
                    'HOSTNAME': hostname,
                    'PROID': proid
                },
            }, {
                'name': 'install-ipa-client-with-otp.sh',
                'vars': {
                    'OTP': otp
                }
            }, {
                'name': 'install-treadmill.sh',
                'vars': {'TREADMILL_RELEASE': tm_release}
            }, {
                'name': 'configure-ldap.sh',
                'vars': {
                    'APP_ROOT': app_root,
                    'IPA_ADMIN_PASSWORD': ipa_admin_password,
                    'DOMAIN': connection.Connection.context.domain,
                    'IPA_SERVER_HOSTNAME': ipa_server_hostname
                },
            },
        ]


class IPA(Configuration):
    def __init__(self, hostname, vpc, ipa_admin_password,
                 tm_release, proid):
        super().__init__()

        self.setup_scripts = [
            {
                'name': 'provision-base.sh',
                'vars': {
                    'DOMAIN': connection.Connection.context.domain,
                    'HOSTNAME': hostname,
                    'REGION': connection.Connection.context.region_name,
                    'PROID': proid,
                    'SUBNET_ID': self.subnet_id,
                },
            }, {
                'name': 'install-treadmill.sh',
                'vars': {'TREADMILL_RELEASE': tm_release}
            }, {
                'name': 'install-ipa-server.sh',
                'vars': {
                    'DOMAIN': connection.Connection.context.domain,
                    'IPA_ADMIN_PASSWORD': ipa_admin_password,
                    'REVERSE_ZONE': vpc.reverse_domain_name(),
                },
            },
        ]


class Zookeeper(Configuration):
    def __init__(self, hostname, ldap_hostname, ipa_server_hostname, otp, idx,
                 proid, cfg_data):
        super().__init__()

        self.setup_scripts = [
            {
                'name': 'provision-base.sh',
                'vars': {
                    'DOMAIN': connection.Connection.context.domain,
                    'HOSTNAME': hostname,
                    'LDAP_HOSTNAME': ldap_hostname,
                    'PROID': proid
                },
            }, {
                'name': 'install-ipa-client-with-otp.sh',
                'vars': {
                    'OTP': otp
                }
            }, {
                'name': 'provision-zookeeper.sh',
                'vars': {
                    'DOMAIN': connection.Connection.context.domain,
                    'IPA_SERVER_HOSTNAME': ipa_server_hostname,
                    'IDX': idx,
                    'CFG_DATA': cfg_data,
                },
            },
        ]


class Node(Configuration):
    def __init__(self, tm_release, app_root,
                 ldap_hostname, otp, with_api, hostname,
                 ipa_admin_password, proid, zk_url):
        super().__init__()

        self.setup_scripts = [
            {
                'name': 'provision-base.sh',
                'vars': {
                    'DOMAIN': connection.Connection.context.domain,
                    'APP_ROOT': app_root,
                    'SUBNET_ID': self.subnet_id,
                    'LDAP_HOSTNAME': ldap_hostname,
                    'HOSTNAME': hostname,
                    'PROID': proid,
                    'ZK_URL': zk_url,
                }
            }, {
                'name': 'install-ipa-client-with-otp.sh',
                'vars': {
                    'OTP': otp
                }
            }, {
                'name': 'install-treadmill.sh',
                'vars': {
                    'TREADMILL_RELEASE': tm_release
                }
            }, {
                'name': 'configure-node.sh',
                'vars': {
                    'APP_ROOT': app_root,
                    'SUBNET_ID': self.subnet_id,
                    'IPA_ADMIN_PASSWORD': ipa_admin_password,
                },
            }
        ]
        if with_api:
            self.setup_scripts.append({
                'name': 'start-api.sh',
            })
