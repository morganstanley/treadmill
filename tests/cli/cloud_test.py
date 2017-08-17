import importlib
import unittest
import click
import click.testing
import mock

from treadmill.infra import constants


class CloudTest(unittest.TestCase):
    def setUp(self):
        self.runner = click.testing.CliRunner()
        self.configure_cli = importlib.import_module(
            'treadmill.cli.cloud').init()

    @mock.patch('treadmill.cli.cloud.vpc.VPC')
    def test_init(self, vpc_mock):
        """
        Test cloud init
        """
        result = self.runner.invoke(
            self.configure_cli, [
                'init',
                '--domain=test.treadmill',
                '--vpc-cidr-block=172.24.0.0/16',
                '--secgroup_name=sg_common',
                '--secgroup_desc=Test'
            ])

        self.assertEqual(result.exit_code, 0)
        vpc_mock.setup.assert_called_once_with(
            cidr_block='172.24.0.0/16',
            secgroup_name='sg_common',
            secgroup_desc='Test',
        )

    @mock.patch('treadmill.cli.cloud.ldap.LDAP')
    @mock.patch('treadmill.cli.cloud.cell.Cell')
    def test_init_cell(self, cell_mock, ldap_mock):
        """
        Test cloud init cell
        """
        cell = cell_mock()
        cell.id = 'sub-123'
        _ldap_mock = ldap_mock()
        result = self.runner.invoke(
            self.configure_cli, [
                'init-cell',
                '--domain=treadmill.org',
                '--key=key',
                '--image-id=img-123',
                '--subnet-id=sub-123',
                '--vpc-id=vpc-123',
                '--cell-cidr-block=172.24.0.0/24',
                '--ipa-admin-password=ipa_pass',
            ])

        self.assertEqual(result.exit_code, 0)
        cell.setup_zookeeper.assert_called_once_with(
            name='TreadmillZookeeper',
            key='key',
            ldap_hostname='treadmillldap1',
            image_id='img-123',
            instance_type=constants.INSTANCE_TYPES['EC2']['micro'],
            subnet_cidr_block='172.24.0.0/24',
            ipa_admin_password='ipa_pass',
        )
        cell.setup_master.assert_called_once_with(
            name='TreadmillMaster',
            key='key',
            count=3,
            image_id='img-123',
            instance_type=constants.INSTANCE_TYPES['EC2']['micro'],
            tm_release='0.1.0',
            ldap_hostname='treadmillldap1',
            app_root='/var/tmp',
            subnet_cidr_block='172.24.0.0/24',
            ipa_admin_password='ipa_pass'
        )
        self.assertEqual(
            ldap_mock.mock_calls[1],
            mock.mock.call(
                name='TreadmillLDAP',
                vpc_id='vpc-123',
            )
        )
        _ldap_mock.setup.assert_called_once_with(
            key='key',
            count=1,
            image_id='img-123',
            instance_type=constants.INSTANCE_TYPES['EC2']['micro'],
            tm_release='0.1.0',
            ldap_hostname='treadmillldap1',
            app_root='/var/tmp',
            cidr_block='172.23.1.0/24',
            subnet_id=None,
            cell_subnet_id='sub-123',
            ipa_admin_password='ipa_pass',
        )

    @mock.patch('treadmill.cli.cloud.ldap.LDAP')
    @mock.patch('treadmill.cli.cloud.cell.Cell')
    def test_init_cell_without_ldap(self, cell_mock, ldap_mock):
        """
        Test cloud init cell without ldap
        """
        cell = cell_mock()
        _ldap_mock = ldap_mock()
        result = self.runner.invoke(
            self.configure_cli, [
                'init-cell',
                '--key=key',
                '--image-id=img-123',
                '--subnet-id=sub-123',
                '--vpc-id=vpc-123',
                '--cell-cidr-block=172.24.0.0/24',
                '--domain=treadmill.org',
                '--without-ldap',
                '--ipa-admin-password=ipa_pass',
            ])

        self.assertEqual(result.exit_code, 0)
        cell.setup_zookeeper.assert_called_once_with(
            name='TreadmillZookeeper',
            key='key',
            ldap_hostname='treadmillldap1',
            image_id='img-123',
            instance_type=constants.INSTANCE_TYPES['EC2']['micro'],
            subnet_cidr_block='172.24.0.0/24',
            ipa_admin_password='ipa_pass',
        )
        cell.setup_master.assert_called_once_with(
            name='TreadmillMaster',
            key='key',
            count=3,
            image_id='img-123',
            instance_type=constants.INSTANCE_TYPES['EC2']['micro'],
            tm_release='0.1.0',
            ldap_hostname='treadmillldap1',
            app_root='/var/tmp',
            subnet_cidr_block='172.24.0.0/24',
            ipa_admin_password='ipa_pass'
        )

        _ldap_mock.setup.assert_not_called()

    @mock.patch('treadmill.cli.cloud.node.Node')
    def test_add_node(self, NodeMock):
        """
        Test add node
        """
        node_mock = NodeMock()
        result = self.runner.invoke(
            self.configure_cli, [
                'add-node',
                '--key=key',
                '--image-id=img-123',
                '--vpc-id=vpc-123',
                '--subnet-id=sub-123',
                '--count=2',
                '--domain=treadmill.org',
                '--ipa-admin-password=Tre@admill1',
            ])

        self.assertEqual(result.exit_code, 0)
        node_mock.setup.assert_called_once_with(
            app_root='/var/tmp/treadmill-node',
            count=2,
            image_id='img-123',
            instance_type=constants.INSTANCE_TYPES['EC2']['large'],
            key='key',
            ldap_hostname='treadmillldap1',
            subnet_id='sub-123',
            tm_release='0.1.0',
            ipa_admin_password='Tre@admill1',
            with_api=False,
        )

    @mock.patch('treadmill.cli.cloud.ipa.IPA')
    def test_init_domain(self, ipa_mock):
        """
        Test cloud init domain
        """
        ipa = ipa_mock()
        result = self.runner.invoke(
            self.configure_cli, [
                'init-domain',
                '--ipa-admin-password=Tre@dmil1',
                '--key=key',
                '--image-id=img-123',
                '--vpc-id=vpc-123',
                '--domain=test.treadmill'
            ])

        self.assertEqual(result.exit_code, 0)
        ipa.setup.assert_called_once_with(
            image_id='img-123',
            count=1,
            cidr_block='172.23.2.0/24',
            ipa_admin_password='Tre@dmil1',
            tm_release='0.1.0',
            key='key',
            instance_type=constants.INSTANCE_TYPES['EC2']['medium'],
            subnet_id=None
        )

    @mock.patch('treadmill.cli.cloud.ipa.IPA')
    def test_delete_domain(self, ipa_mock):
        """
        Test cloud delete domain
        """
        ipa = ipa_mock()
        result = self.runner.invoke(
            self.configure_cli, [
                'delete',
                'domain',
                '--vpc-id=vpc-123',
                '--subnet-id=sub-123',
                '--domain=treadmill.org',
            ])

        self.assertEqual(result.exit_code, 0)
        ipa.destroy.assert_called_once_with(
            subnet_id='sub-123'
        )

    @mock.patch('treadmill.cli.cloud.node.Node')
    def test_delete_node_by_instance_id(self, node_mock):
        """
        Test cloud delete node
        """
        _node_mock = node_mock()
        result = self.runner.invoke(
            self.configure_cli, [
                'delete',
                'node',
                '--vpc-id=vpc-123',
                '--instance-id=instance-123',
                '--name=foo',
                '--domain=treadmill.org',
            ])
        self.assertEqual(result.exit_code, 0)
        _node_mock.destroy.assert_called_once_with(
            instance_id='instance-123'
        )
