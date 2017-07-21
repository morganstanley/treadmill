"""
Integration test for EC2 cell setup.
"""

import ast
import unittest
import importlib
import click
import click.testing
from botocore.exceptions import ClientError
import pkg_resources

from treadmill.infra import vpc


class CellCLITest(unittest.TestCase):
    """Tests EC2 cell setup."""

    def setUp(self):
        self.runner = click.testing.CliRunner()
        self.configure_cli = importlib.import_module(
            'treadmill.cli.cloud'
        ).init()

    def tearDown(self):
        if not self.destroy_attempted:
            self.runner.invoke(
                self.configure_cli, [
                    'delete',
                    'vpc',
                    '--vpc-id=' + self.vpc_id,
                    '--domain=treadmill.org'
                ]
            )

    def test_setup_cell(self):
        self.destroy_attempted = False
        options_fixture_file = pkg_resources.resource_filename(
            __name__, 'init_cell_options.yml'
        )
        result_init = self.runner.invoke(
            self.configure_cli, [
                'init',
                '-f=' + options_fixture_file
            ]
        )
        cell_info = {}
        vpc_info = {}

        try:
            vpc_info = ast.literal_eval(result_init.output)
        except Exception as e:
            if result_init.exception:
                print(result_init.exception)
            else:
                print(e)

        self.vpc_id = vpc_info['VpcId']
        self.assertIsNotNone(vpc_info['VpcId'])
        self.assertEqual(vpc_info['Subnets'], [])

        result_cell_init = self.runner.invoke(
            self.configure_cli, [
                'init-cell',
                '--key=ms_treadmill_dev',
                '--image-id=ami-9e2f0988',
                '--vpc-id=' + vpc_info['VpcId'],
                '--cell-cidr-block=172.23.0.0/24',
                '--domain=treadmill.org',
                '--ipa-admin-password=Tre@dmill1',
            ]
        )

        result = {}
        try:
            result = ast.literal_eval(result_cell_init.output)
        except Exception as e:
            if result_cell_init.exception:
                print(result_cell_init.exception)
            else:
                print(e)

        cell_info = result['Cell']
        ldap_info = result['Ldap']

        _vpc = vpc.VPC(id=vpc_info['VpcId'])
        _vpc_info = _vpc.show()

        self.assertEqual(cell_info['VpcId'], vpc_info['VpcId'])
        self.assertEqual(cell_info['VpcId'], ldap_info['VpcId'])
        self.assertEqual(len(cell_info['Instances']), 6)
        self.assertEqual(len(ldap_info['Instances']), 1)
        self.assertCountEqual(
            [i['Name'] for i in cell_info['Instances']],
            ['TreadmillMaster1', 'TreadmillMaster2', 'TreadmillMaster3',
             'TreadmillZookeeper1', 'TreadmillZookeeper2',
             'TreadmillZookeeper3']
        )
        zk_subnet_ids = set([
            i['SubnetId'] for i in cell_info['Instances'] if i['Name'][:-1]
            in 'TreadmillZookeeper'
        ])

        master_subnet_ids = set([
            i['SubnetId'] for i in cell_info['Instances'] if i['Name'][:-1]
            in 'TreadmillMaster'
        ])

        ldap_subnet_ids = set([
            i['SubnetId'] for i in ldap_info['Instances'] if i['Name'][:-1]
            in 'TreadmillLDAP'
        ])

        self.assertEqual(len(zk_subnet_ids), 1)
        self.assertEqual(len(ldap_subnet_ids), 1)
        self.assertEqual(len(master_subnet_ids), 1)
        self.assertEqual(master_subnet_ids, zk_subnet_ids)
        self.assertNotEqual(master_subnet_ids, ldap_subnet_ids)
        self.assertEqual(len(_vpc_info['Subnets']), 2)
        self.assertCountEqual(_vpc_info['Subnets'],
                              [list(zk_subnet_ids)[0],
                               list(ldap_subnet_ids)[0]])

        self.runner.invoke(
            self.configure_cli, [
                'delete',
                'cell',
                '--subnet-id=' + cell_info['SubnetId'],
                '--vpc-id=' + vpc_info['VpcId'],
                '--domain=treadmill.org'
            ]
        )
        self.runner.invoke(
            self.configure_cli, [
                'delete',
                'cell',
                '--subnet-id=' + ldap_info['SubnetId'],
                '--vpc-id=' + vpc_info['VpcId'],
                '--domain=treadmill.org'
            ]
        )
        _vpc.instances = None
        _vpc.subnet_ids = []
        _vpc_info = _vpc.show()
        self.assertEqual(len(_vpc_info['Instances']), 0)
        self.assertEqual(len(_vpc_info['Subnets']), 0)

        self.runner.invoke(
            self.configure_cli, [
                'delete',
                'vpc',
                '--vpc-id=' + vpc_info['VpcId'],
                '--domain=treadmill.org'
            ]
        )
        self.destroy_attempted = True

        with self.assertRaises(ClientError) as error:
            _vpc.ec2_conn.describe_vpcs(
                VpcIds=[vpc_info['VpcId']]
            )
        self.assertEqual(
            error.exception.response['Error']['Code'],
            'InvalidVpcID.NotFound'
        )


if __name__ == '__main__':
    unittest.main()
