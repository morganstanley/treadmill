"""
Integration test for EC2 ipa setup.
"""

import ast
import unittest
import importlib
import click
import click.testing
from botocore.exceptions import ClientError
from treadmill.infra import vpc


class IPATest(unittest.TestCase):
    """Tests EC2 cell setup."""

    def setUp(self):
        self.runner = click.testing.CliRunner()
        self.configure_cli = importlib.import_module(
            'treadmill.cli.cloud').init()

    def tearDown(self):
        if not self.destroy_attempted:
            self.runner.invoke(
                self.configure_cli, [
                    'delete',
                    'vpc',
                    '--vpc-id=' + self.vpc_id,
                    '--domain=ms.treadmill'
                ]
            )

    def test_setup_ipa(self):
        self.destroy_attempted = False
        result_init = self.runner.invoke(self.configure_cli, ['init'])
        subnet_info = {}
        vpc_info = {}

        try:
            print(result_init.output)
            vpc_info = ast.literal_eval(result_init.output)
        except Exception as e:
            if result_init.exception:
                print(result_init.exception)
            else:
                print(e)

        self.vpc_id = vpc_info['VpcId']
        self.assertIsNotNone(vpc_info['VpcId'])
        self.assertEqual(vpc_info['Cells'], [])

        result_domain_init = self.runner.invoke(
            self.configure_cli, [
                'init-domain',
                '--key=ms_treadmill_dev',
                '--image-id=ami-9e2f0988',
                '--vpc-id=' + vpc_info['VpcId'],
                '--subnet-cidr-block=172.23.0.0/24',
                '--ipa-admin-password=secret'
            ]
        )

        try:
            subnet_info = ast.literal_eval(result_domain_init.output)
        except Exception as e:
            if result_domain_init.exception:
                print(result_domain_init.exception)
            else:
                print(e)

        _vpc = vpc.VPC(id=vpc_info['VpcId'], domain='ms.treadmill')
        _vpc_info = _vpc.show()
        self.assertEqual(subnet_info['VpcId'], vpc_info['VpcId'])
        self.assertEqual(len(subnet_info['Instances']), 1)
        self.assertCountEqual(
            [i['Name'] for i in subnet_info['Instances']],
            ['TreadmillIPA1']
        )
        self.assertIsNotNone(subnet_info['SubnetId'])
        self.assertEqual(len(_vpc_info['Cells']), 1)
        self.assertEqual(_vpc_info['Cells'][0], subnet_info['SubnetId'])

        self.runner.invoke(
            self.configure_cli, [
                'delete',
                'domain',
                '--vpc-id=' + vpc_info['VpcId'],
                '--subnet-id=' + subnet_info['SubnetId']
            ]
        )

        self.runner.invoke(
            self.configure_cli, [
                'delete',
                'vpc',
                '--vpc-id=' + vpc_info['VpcId'],
                '--domain=' + _vpc.domain
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
