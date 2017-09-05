"""
Integration test for EC2 ipa setup.
"""

import ast
import unittest
import importlib
import click
import click.testing
import time
from botocore.exceptions import ClientError
from treadmill.infra import vpc, subnet


class IPATest(unittest.TestCase):
    """Tests EC2 cell setup."""

    def setUp(self):
        self.vpc_name = 'IntegrationTest-' + str(time.time())
        self.runner = click.testing.CliRunner()
        self.configure_cli = importlib.import_module(
            'treadmill.cli.cloud').init()

    def tearDown(self):
        if not self.destroy_attempted:
            self.runner.invoke(
                self.configure_cli, [
                    '--domain=treadmill.org',
                    'delete',
                    'vpc',
                    '--vpc-name=' + self.vpc_name,
                ],
                obj={}
            )

    def test_setup_ipa_and_ldap_in_same_subnet(self):
        self.destroy_attempted = False
        result_init = self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'init',
                'vpc',
                '--name=' + self.vpc_name
            ],
            obj={}
        )
        subnet_info = {}
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

        result_domain_init = self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'init',
                'domain',
                '--tm-release=0.1.0',
                '--key=ms_treadmill_dev',
                '--image=RHEL-7.4',
                '--vpc-name=' + self.vpc_name,
                '--subnet-cidr-block=172.23.0.0/24',
                '--ipa-admin-password=Tre@dmill1',
                '--subnet-name=TreadmillIPA'
            ],
            obj={}
        )

        try:
            subnet_info = ast.literal_eval(result_domain_init.output)
        except Exception as e:
            if result_domain_init.exception:
                print(result_domain_init.exception)
            else:
                print(e)

        _vpc = vpc.VPC(id=vpc_info['VpcId'])
        vpc_info = _vpc.show()
        self.assertEqual(subnet_info['VpcId'], vpc_info['VpcId'])
        self.assertEqual(len(subnet_info['Instances']), 1)
        self.assertCountEqual(
            [i['Name'] for i in subnet_info['Instances']],
            ['TreadmillIPA1']
        )
        self.assertIsNotNone(subnet_info['SubnetId'])
        self.assertEqual(len(vpc_info['Subnets']), 1)
        self.assertEqual(vpc_info['Subnets'][0], subnet_info['SubnetId'])

        result_ldap_init = self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'init',
                'ldap',
                '--tm-release=0.1.0',
                '--key=ms_treadmill_dev',
                '--image=RHEL-7.4',
                '--vpc-name=' + self.vpc_name,
                '--subnet-name=TreadmillIPA',
                '--ipa-admin-password=Tre@dmill1',
            ],
            obj={}
        )

        try:
            ldap_subnet_info = ast.literal_eval(result_ldap_init.output)
        except Exception as e:
            if result_ldap_init.exception:
                print(result_ldap_init.exception)
            else:
                print(e)

        self.assertEqual(ldap_subnet_info['SubnetId'], subnet_info['SubnetId'])
        self.assertEqual(len(ldap_subnet_info['Instances']), 2)
        self.assertCountEqual(
            [i['Name'] for i in ldap_subnet_info['Instances']],
            ['TreadmillIPA1', 'TreadmillLDAP1']
        )

        self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'delete',
                'domain',
                '--vpc-name=' + self.vpc_name,
                '--subnet-name=TreadmillIPA',
            ],
            obj={}
        )

        _subnet = subnet.Subnet(id=subnet_info['SubnetId'])
        _subnet_resources = _subnet.show()

        self.assertEqual(len(_subnet_resources['Instances']), 1)
        self.assertCountEqual(
            [i['Name'] for i in _subnet_resources['Instances']],
            ['TreadmillLDAP1']
        )

        self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'delete',
                'ldap',
                '--vpc-name=' + self.vpc_name,
                '--subnet-name=TreadmillIPA',
            ],
            obj={}
        )
        _vpc.subnet_ids = []
        vpc_info = _vpc.show()

        self.assertEqual(len(vpc_info['Subnets']), 0)

        self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'delete',
                'vpc',
                '--vpc-name=' + self.vpc_name,
            ],
            obj={}
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

    def test_setup_ipa_and_ldap_in_different_subnets(self):
        self.destroy_attempted = False
        result_init = self.runner.invoke(
            self.configure_cli,
            [
                '--domain=treadmill.org',
                'init',
                'vpc',
                '--name=' + self.vpc_name
            ],
            obj={}
        )
        subnet_info = {}
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

        result_domain_init = self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'init',
                'domain',
                '--tm-release=0.1.0',
                '--key=ms_treadmill_dev',
                '--image=RHEL-7.4',
                '--vpc-name=' + self.vpc_name,
                '--subnet-cidr-block=172.23.0.0/24',
                '--ipa-admin-password=Tre@dmill1',
                '--subnet-name=TreadmillIPA'
            ],
            obj={}
        )

        try:
            subnet_info = ast.literal_eval(result_domain_init.output)
        except Exception as e:
            if result_domain_init.exception:
                print(result_domain_init.exception)
            else:
                print(e)

        _vpc = vpc.VPC(id=vpc_info['VpcId'])
        vpc_info = _vpc.show()
        self.assertEqual(subnet_info['VpcId'], vpc_info['VpcId'])
        self.assertEqual(len(subnet_info['Instances']), 1)
        self.assertCountEqual(
            [i['Name'] for i in subnet_info['Instances']],
            ['TreadmillIPA1']
        )
        self.assertIsNotNone(subnet_info['SubnetId'])
        self.assertEqual(len(vpc_info['Subnets']), 1)
        self.assertEqual(vpc_info['Subnets'][0], subnet_info['SubnetId'])

        result_ldap_init = self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'init',
                'ldap',
                '--tm-release=0.1.0',
                '--key=ms_treadmill_dev',
                '--image=RHEL-7.4',
                '--vpc-name=' + self.vpc_name,
                '--ipa-admin-password=Tre@dmill1',
                '--subnet-name=TreadmillLDAP'
            ],
            obj={}
        )

        try:
            ldap_subnet_info = ast.literal_eval(result_ldap_init.output)
        except Exception as e:
            if result_ldap_init.exception:
                print(result_ldap_init.exception)
            else:
                print(e)

        _vpc.subnet_ids = None
        vpc_info = _vpc.show()

        self.assertEqual(ldap_subnet_info['VpcId'], vpc_info['VpcId'])
        self.assertEqual(len(ldap_subnet_info['Instances']), 1)
        self.assertCountEqual(
            [i['Name'] for i in ldap_subnet_info['Instances']],
            ['TreadmillLDAP1']
        )
        self.assertIsNotNone(ldap_subnet_info['SubnetId'])

        self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'delete',
                'domain',
                '--vpc-name=' + self.vpc_name,
                '--subnet-name=TreadmillIPA',
            ],
            obj={}
        )

        _vpc.subnet_ids = None
        vpc_info = _vpc.show()

        self.assertEqual(len(vpc_info['Subnets']), 1)

        self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'delete',
                'ldap',
                '--vpc-name=' + self.vpc_name,
                '--subnet-name=TreadmillLDAP',
            ],
            obj={}
        )
        _vpc.subnet_ids = []
        vpc_info = _vpc.show()

        self.assertEqual(len(vpc_info['Subnets']), 0)

        self.runner.invoke(
            self.configure_cli, [
                '--domain=treadmill.org',
                'delete',
                'vpc',
                '--vpc-name=' + self.vpc_name,
            ],
            obj={}
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
