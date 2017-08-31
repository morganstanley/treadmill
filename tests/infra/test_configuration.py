"""
Unit test for EC2 configuration.
"""

import unittest
import mock
import io

from treadmill.infra import configuration, SCRIPT_DIR


class ConfigurationTest(unittest.TestCase):
    """Tests configuration"""

    def setUp(self):
        with open(SCRIPT_DIR + 'init.sh', 'r') as data:
            self.init_script_data = data.read()

    @mock.patch('builtins.open', create=True)
    def test_get_userdata(self, open_mock):
        open_mock.side_effect = [
            io.StringIO(self.init_script_data),
            io.StringIO('{{ DOMAIN }}'),
            io.StringIO('{{ CELL }}'),
        ]

        config = configuration.Configuration([])
        userdata = config.get_userdata()
        self.assertEquals(userdata, '')

        config = configuration.Configuration([
            {'name': 'script1.sh', 'vars': {'DOMAIN': 'test.treadmill'}},
            {'name': 'script2.sh', 'vars': {'CELL': 'mycell'}},
        ])
        userdata = config.get_userdata()

        self.assertEquals(
            userdata,
            self.init_script_data + 'test.treadmill\nmycell\n'
        )


class MasterTest(unittest.TestCase):
    """Tests master configuration"""

    @mock.patch('builtins.open', create=True)
    def test_master_configuration_script_data(self, open_mock):
        config = configuration.Master('', '', '', '', '', '')
        expected_script_data = {
            'provision-base.sh': [
                'DOMAIN', 'NAME', 'SUBNET_ID', 'LDAP_HOSTNAME', 'APP_ROOT',
            ],
            'install-ipa-client.sh': [],
            'install-treadmill.sh': ['TREADMILL_RELEASE'],
            'configure-master.sh': [
                'SUBNET_ID', 'APP_ROOT', 'IPA_ADMIN_PASSWORD'
            ],
        }

        self.assertCountEqual(
            [s['name'] for s in config.setup_scripts],
            expected_script_data.keys()
        )

        # Make sure all the scripts have required variables to replace, for
        # jinja
        for script_data in config.setup_scripts:
            self.assertCountEqual(
                expected_script_data[script_data['name']],
                script_data['vars'].keys()
            )


class LDAPTest(unittest.TestCase):
    """Tests master configuration"""

    @mock.patch('builtins.open', create=True)
    def test_ldap_configuration_script_data(self, open_mock):
        config = configuration.LDAP('', '', '', '', '', '')
        expected_script_data = {
            'provision-base.sh': [
                'DOMAIN', 'NAME', 'SUBNET_ID', 'LDAP_HOSTNAME', 'APP_ROOT',
            ],
            'install-ipa-client.sh': [],
            'install-treadmill.sh': ['TREADMILL_RELEASE'],
            'configure-ldap.sh': [
                'SUBNET_ID', 'APP_ROOT', 'IPA_ADMIN_PASSWORD', 'DOMAIN'
            ],
        }

        self.assertCountEqual(
            [s['name'] for s in config.setup_scripts],
            expected_script_data.keys()
        )

        # Make sure all the scripts have required variables to replace, for
        # jinja
        for script_data in config.setup_scripts:
            self.assertCountEqual(
                expected_script_data[script_data['name']],
                script_data['vars'].keys()
            )


class IPATest(unittest.TestCase):
    """Tests ipa configuration"""

    @mock.patch('builtins.open', create=True)
    def test_ipa_configuration_script_data(self, open_mock):
        config = configuration.IPA(
            ipa_admin_password='admin-password',
            tm_release='some-release',
            name='ipa',
            cell='subnet-id',
            vpc=mock.Mock(),
        )
        expected_script_data = {
            'provision-base.sh': ['DOMAIN', 'NAME'],
            'install-treadmill.sh': ['TREADMILL_RELEASE'],
            'install-ipa-server.sh': [
                'DOMAIN', 'IPA_ADMIN_PASSWORD', 'CELL', 'REVERSE_ZONE',
            ],
        }

        self.assertCountEqual(
            [s['name'] for s in config.setup_scripts],
            expected_script_data.keys()
        )

        # Make sure all the scripts have required variables to replace, for
        # jinja
        for script_data in config.setup_scripts:
            self.assertCountEqual(
                expected_script_data[script_data['name']],
                script_data['vars'].keys()
            )


class ZookeeperTest(unittest.TestCase):
    """Tests zookeeper configuration"""

    @mock.patch('builtins.open', create=True)
    def test_zookeeper_configuration_script_data(self, open_mock):
        config = configuration.Zookeeper(
            name='zookeeper',
            ldap_hostname='ldap_host',
            ipa_admin_password='ipa_admin_password'
        )
        expected_script_data = {
            'provision-base.sh': ['DOMAIN', 'NAME', 'LDAP_HOSTNAME'],
            'install-ipa-client.sh': [],
            'provision-zookeeper.sh': ['DOMAIN', 'IPA_ADMIN_PASSWORD'],
        }

        self.assertCountEqual(
            [s['name'] for s in config.setup_scripts],
            expected_script_data.keys()
        )

        # Make sure all the scripts have required variables to replace, for
        # jinja
        for script_data in config.setup_scripts:
            self.assertCountEqual(
                expected_script_data[script_data['name']],
                script_data['vars'].keys()
            )


class NodeTest(unittest.TestCase):
    """Tests node configuration"""

    @mock.patch('builtins.open', create=True)
    def test_node_configuration_script_data(self, open_mock):
        config = configuration.Node(
            name='node',
            tm_release='tm_release',
            app_root='/var/tmp',
            subnet_id='sub-123',
            ldap_hostname='ldap_host',
            ipa_admin_password='Tre@admill1',
            with_api=False,
        )
        expected_script_data = {
            'provision-base.sh': ['DOMAIN', 'NAME', 'APP_ROOT', 'SUBNET_ID',
                                  'LDAP_HOSTNAME', 'ROLE'],
            'install-ipa-client.sh': [],
            'install-treadmill.sh': ['TREADMILL_RELEASE'],
            'configure-node.sh': [
                'APP_ROOT', 'SUBNET_ID', 'IPA_ADMIN_PASSWORD'
            ],
        }

        self.assertCountEqual(
            [s['name'] for s in config.setup_scripts],
            expected_script_data.keys()
        )

        # Make sure all the scripts have required variables to replace, for
        # jinja
        for script_data in config.setup_scripts:
            self.assertCountEqual(
                expected_script_data[script_data['name']],
                script_data['vars'].keys()
            )
