import importlib
import unittest
import click
import click.testing
import mock

from treadmill.infra import constants, connection


class CloudTest(unittest.TestCase):
    def setUp(self):
        connection.Connection.context.region_name = 'foobar'
        self.vpc_id_mock = 'vpc-123'
        self.vpc_name = 'vpc-name'
        self.runner = click.testing.CliRunner()
        self.configure_cli = importlib.import_module(
            'treadmill.cli.cloud').init()

    @mock.patch('treadmill.cli.cloud.vpc.VPC')
    def test_init_vpc(self, vpc_mock):
        """
        Test cloud init vpc
        """
        vpc_mock.get_id_from_name = mock.Mock(return_value=None)
        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=test.treadmill',
                'init',
                'vpc',
                '--vpc-cidr-block=172.24.0.0/16',
                '--secgroup_name=sg_common',
                '--secgroup_desc=Test',
                '--name=' + self.vpc_name
            ],
            obj={}
        )
        self.assertEqual(result.exit_code, 0)
        vpc_mock.get_id_from_name.assert_called_once_with(self.vpc_name)
        vpc_mock.setup.assert_called_once_with(
            name=self.vpc_name,
            cidr_block='172.24.0.0/16',
            secgroup_name='sg_common',
            secgroup_desc='Test',
        )

    @mock.patch('treadmill.cli.cloud.vpc.VPC')
    def test_init_vpc_with_duplicate_vpc_name(self, vpc_mock):
        """
        Test cloud init vpc
        """
        vpc_mock.get_id_from_name = mock.Mock(return_value='some-vpc-id')

        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=test.treadmill',
                'init',
                'vpc',
                '--vpc-cidr-block=172.24.0.0/16',
                '--secgroup_name=sg_common',
                '--secgroup_desc=Test',
                '--name=' + self.vpc_name
            ],
            obj={}
        )
        self.assertIn('Error: Invalid value for "--name"', result.output)
        vpc_mock.get_id_from_name.assert_called_once_with(self.vpc_name)
        vpc_mock.setup.assert_not_called()

    @mock.patch('treadmill.cli.cloud.vpc.VPC')
    @mock.patch('treadmill.cli.cloud.ldap.LDAP')
    @mock.patch('treadmill.cli.cloud.cell.Cell')
    def test_init_cell(self, cell_mock, ldap_mock, vpc_mock):
        """
        Test cloud init cell
        """
        vpc_mock.get_id_from_name = mock.Mock(return_value=self.vpc_id_mock)
        cell = cell_mock()
        cell.id = 'sub-123'
        _ldap_mock = ldap_mock()
        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'init',
                'cell',
                '--tm-release=0.1.0',
                '--key=key',
                '--image=img-123',
                '--subnet-id=sub-123',
                '--vpc-name=' + self.vpc_name,
                '--cell-cidr-block=172.24.0.0/24',
                '--ipa-admin-password=ipa_pass',
            ],
            obj={}
        )

        self.assertEqual(result.exit_code, 0)
        vpc_mock.get_id_from_name.assert_called_once_with(self.vpc_name)
        cell.setup_zookeeper.assert_called_once_with(
            name='TreadmillZookeeper',
            key='key',
            ldap_hostname='treadmillldap1',
            image='img-123',
            instance_type=constants.INSTANCE_TYPES['EC2']['micro'],
            subnet_cidr_block='172.24.0.0/24',
            ipa_admin_password='ipa_pass',
        )
        cell.setup_master.assert_called_once_with(
            name='TreadmillMaster',
            key='key',
            count=3,
            image='img-123',
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
            image='img-123',
            instance_type=constants.INSTANCE_TYPES['EC2']['micro'],
            tm_release='0.1.0',
            ldap_hostname='treadmillldap1',
            app_root='/var/tmp',
            cidr_block='172.23.1.0/24',
            subnet_id=None,
            cell_subnet_id='sub-123',
            ipa_admin_password='ipa_pass',
        )

    @mock.patch('treadmill.cli.cloud.vpc.VPC')
    @mock.patch('treadmill.cli.cloud.ldap.LDAP')
    @mock.patch('treadmill.cli.cloud.cell.Cell')
    def test_init_cell_without_ldap(self, cell_mock, ldap_mock, vpc_mock):
        """
        Test cloud init cell without ldap
        """
        vpc_mock.get_id_from_name = mock.Mock(return_value=self.vpc_id_mock)
        cell = cell_mock()
        _ldap_mock = ldap_mock()

        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'init',
                'cell',
                '--tm-release=0.1.0',
                '--key=key',
                '--image=img-123',
                '--subnet-id=sub-123',
                '--vpc-name=' + self.vpc_name,
                '--cell-cidr-block=172.24.0.0/24',
                '--without-ldap',
                '--ipa-admin-password=ipa_pass',
            ],
            obj={}
        )

        self.assertEqual(result.exit_code, 0)
        vpc_mock.get_id_from_name.assert_called_once_with(self.vpc_name)
        cell.setup_zookeeper.assert_called_once_with(
            name='TreadmillZookeeper',
            key='key',
            ldap_hostname='treadmillldap1',
            image='img-123',
            instance_type=constants.INSTANCE_TYPES['EC2']['micro'],
            subnet_cidr_block='172.24.0.0/24',
            ipa_admin_password='ipa_pass',
        )
        cell.setup_master.assert_called_once_with(
            name='TreadmillMaster',
            key='key',
            count=3,
            image='img-123',
            instance_type=constants.INSTANCE_TYPES['EC2']['micro'],
            tm_release='0.1.0',
            ldap_hostname='treadmillldap1',
            app_root='/var/tmp',
            subnet_cidr_block='172.24.0.0/24',
            ipa_admin_password='ipa_pass'
        )

        _ldap_mock.setup.assert_not_called()

    @mock.patch('treadmill.cli.cloud.vpc.VPC')
    @mock.patch('treadmill.cli.cloud.node.Node')
    def test_add_node(self, NodeMock, vpc_mock):
        """
        Test add node
        """
        vpc_mock.get_id_from_name = mock.Mock(return_value=self.vpc_id_mock)
        node_mock = NodeMock()
        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'init',
                'node',
                '--tm-release=0.1.0',
                '--key=key',
                '--image=img-123',
                '--vpc-name=' + self.vpc_name,
                '--subnet-id=sub-123',
                '--count=2',
                '--ipa-admin-password=Tre@admill1',
            ],
            obj={}
        )

        self.assertEqual(result.exit_code, 0)

        vpc_mock.get_id_from_name.assert_called_once_with(self.vpc_name)
        node_mock.setup.assert_called_once_with(
            app_root='/var/tmp/treadmill-node',
            count=2,
            image='img-123',
            instance_type=constants.INSTANCE_TYPES['EC2']['large'],
            key='key',
            ldap_hostname='treadmillldap1',
            subnet_id='sub-123',
            tm_release='0.1.0',
            ipa_admin_password='Tre@admill1',
            with_api=False,
        )

    @mock.patch('treadmill.cli.cloud.vpc.VPC')
    @mock.patch('treadmill.cli.cloud.ipa.IPA')
    def test_init_domain(self, ipa_mock, vpc_mock):
        """
        Test cloud init domain
        """
        vpc_mock.get_id_from_name = mock.Mock(return_value=self.vpc_id_mock)
        ipa = ipa_mock()
        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=test.treadmill',
                'init',
                'domain',
                '--tm-release=0.1.0',
                '--ipa-admin-password=Tre@dmil1',
                '--key=key',
                '--image=img-123',
                '--vpc-name=' + self.vpc_name,
            ],
            obj={}
        )

        self.assertEqual(result.exit_code, 0)
        ipa.setup.assert_called_once_with(
            image='img-123',
            count=1,
            cidr_block='172.23.2.0/24',
            ipa_admin_password='Tre@dmil1',
            tm_release='0.1.0',
            key='key',
            instance_type=constants.INSTANCE_TYPES['EC2']['medium'],
            subnet_id=None
        )

    @mock.patch('treadmill.cli.cloud.vpc.VPC')
    @mock.patch('treadmill.cli.cloud.ipa.IPA')
    def test_delete_domain(self, ipa_mock, vpc_mock):
        """
        Test cloud delete domain
        """
        vpc_mock.get_id_from_name = mock.Mock(return_value=self.vpc_id_mock)
        ipa = ipa_mock()
        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'delete',
                'domain',
                '--vpc-name=' + self.vpc_name,
                '--subnet-id=sub-123',
            ],
            obj={}
        )

        self.assertEqual(result.exit_code, 0)
        ipa.destroy.assert_called_once_with(
            subnet_id='sub-123'
        )

    @mock.patch('treadmill.cli.cloud.vpc.VPC')
    @mock.patch('treadmill.cli.cloud.node.Node')
    def test_delete_node_by_instance_id(self, node_mock, vpc_mock):
        """
        Test cloud delete node
        """
        vpc_mock.get_id_from_name = mock.Mock(return_value=self.vpc_id_mock)
        _node_mock = node_mock()
        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'delete',
                'node',
                '--vpc-name=' + self.vpc_name,
                '--instance-id=instance-123',
                '--name=foo',
            ],
            obj={}
        )
        self.assertEqual(result.exit_code, 0)
        _node_mock.destroy.assert_called_once_with(
            instance_id='instance-123'
        )

    @mock.patch('treadmill.cli.cloud.vpc.VPC')
    def test_list_all_vpc(self, vpc_mock):
        """
        Test cloud list all vpc
        """
        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'list',
                'vpc',
            ],
            obj={}
        )
        self.assertEqual(result.exit_code, 0)
        vpc_mock.all.assert_called_once()

    @mock.patch('treadmill.cli.cloud.vpc.VPC')
    def test_list_vpc(self, vpc_mock):
        """
        Test cloud list vpc
        """
        vpc_mock.get_id_from_name = mock.Mock(return_value=self.vpc_id_mock)
        _vpc_mock = vpc_mock()

        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'list',
                'vpc',
                '--vpc-name=' + self.vpc_name,
            ],
            obj={}
        )
        self.assertEqual(result.exit_code, 0)
        self.assertEquals(vpc_mock.mock_calls[2],
                          mock.mock.call(id=self.vpc_id_mock))
        _vpc_mock.show.assert_called_once()

    @mock.patch('treadmill.cli.cloud.vpc.VPC')
    @mock.patch('treadmill.cli.cloud.subnet.Subnet')
    def test_list_cell(self, subnet_mock, vpc_mock):
        """
        Test cloud list cell
        """
        _subnet_mock = subnet_mock()
        _vpc_mock = vpc_mock()
        vpc_mock.all = mock.Mock(return_value=[vpc_mock(), vpc_mock()])

        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=foo.bar',
                'list',
                'cell',
                '--subnet-id=subnet-123',
            ],
            obj={}
        )

        self.assertEquals(result.exit_code, 0)
        _subnet_mock.show.assert_called_once()
        vpc_mock.get_id_from_name = mock.Mock(return_value=self.vpc_id_mock)
        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=foo.bar',
                'list',
                'cell',
                '--vpc-name=' + self.vpc_name,
            ],
            obj={}
        )
        self.assertEquals(result.exit_code, 0)
        _vpc_mock.list_cells.assert_called_once()

        result = self.runner.invoke(
            self.configure_cli, [
                '--domain=foo.bar',
                'list',
                'cell',
            ],
            obj={}
        )
        self.assertEquals(result.exit_code, 0)
        self.assertEquals(_vpc_mock.list_cells.call_count, 3)

        @mock.patch('treadmill.cli.cloud.vpc.VPC')
        @mock.patch('treadmill.cli.cloud.subnet.Subnet')
        def test_delete_cell(self, subnet_mock, vpc_mock):
            _vpc_mock = vpc_mock()
            _subnet_mock = subnet_mock()
            _vpc_mock.hosted_zone_id = 'hostedzone/123'
            _vpc_mock.reverse_hosted_zone_id = 'hostedzone/456'
            _vpc_mock.list_cells = mock.Mock(return_value=['subnet-123'])

            result = self.runner.invoke(
                self.configure_cli, [
                    '--domain=foo.bar',
                    'delete',
                    'cell',
                    '--vpc-name=' + self.vpc_name,
                    '--subnet-id=subnet-123'
                ]
            )

            self.assertEquals(result.exit_code, 0)
            _subnet_mock.destroy.assert_called_once_with(
                hosted_zone_id='hostedzone/123',
                reverse_hosted_zone_id='hostedzone/456'
            )

            with self.assertRaises(click.BadParameter):
                self.runner.invoke(
                    self.configure_cli, [
                        '--domain=foo.bar',
                        'delete',
                        'cell',
                        '--vpc-name=' + self.vpc_name,
                        '--subnet-id=subnet-456'
                    ]
                )
