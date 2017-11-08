"""
Unit test for EC2 ipa.
"""

import unittest
import mock

from treadmill.infra.setup.ipa import IPA
from treadmill.infra import constants


class IPATest(unittest.TestCase):
    """Tests EC2 ipa setup."""

    @mock.patch('time.time', mock.Mock(return_value=1000))
    @mock.patch('treadmill.infra.subnet.Subnet')
    @mock.patch('treadmill.infra.get_iam_role')
    @mock.patch('treadmill.infra.configuration.IPA')
    @mock.patch('treadmill.infra.connection.Connection')
    @mock.patch('treadmill.infra.vpc.VPC')
    @mock.patch('treadmill.infra.instances.Instances')
    def test_setup_ipa(self, InstancesMock,
                       VPCMock, ConnectionMock, IPAConfigurationMock,
                       get_iam_role_mock, SubnetMock):
        ConnectionMock.context.domain = 'foo.bar'
        instance_mock = mock.Mock(metadata={'PrivateIpAddress': '1.1.1.1'})
        instance_mock.name = 'ipa'
        instance_mock.running_status = mock.Mock(return_value='passed')
        instances_mock = mock.Mock(instances=[instance_mock])
        InstancesMock.create = mock.Mock(return_value=instances_mock)
        conn_mock = ConnectionMock('route53')
        _vpc_id_mock = 'vpc-id'
        _vpc_mock = VPCMock(id=_vpc_id_mock)
        _vpc_mock.secgroup_ids = ['secgroup_id']
        _vpc_mock.gateway_ids = [123]

        conn_mock.describe_instance_status = mock.Mock(
            return_value={
                'InstanceStatuses': [
                    {'InstanceStatus': {'Details': [{'Status': 'passed'}]}}
                ]
            }
        )

        _private_ip = '1.1.1.1'
        _subnet_mock = mock.Mock(
            persisted=False,
            id='subnet-id',
            vpc_id=_vpc_id_mock,
            name='subnet-name',
            get_instances=mock.Mock(return_value=instances_mock)
        )
        SubnetMock.get = mock.Mock(return_value=_subnet_mock)

        _ipa_configuration_mock = IPAConfigurationMock()
        _ipa_configuration_mock.get_userdata = mock.Mock(
            return_value='user-data-script'
        )
        ipa = IPA(
            name='ipa',
            vpc_id=_vpc_id_mock,
        )
        ipa.setup(
            image='foo-123',
            count=1,
            cidr_block='cidr-block',
            key='some-key',
            tm_release='release',
            ipa_admin_password='ipa-admin-password',
            instance_type='small',
            proid='foobar',
            subnet_name='sub-name'
        )

        get_iam_role_mock.assert_called_once_with(
            name=constants.IPA_EC2_IAM_ROLE,
            create=True
        )

        instance_mock.running_status.assert_called_once_with(refresh=True)
        _subnet_mock.refresh.assert_called()
        _subnet_mock.get_instances.assert_called_once_with(
            refresh=True,
            role='IPA'
        )

        _vpc_mock.create_security_group.assert_called_once()
        _vpc_mock.add_secgrp_rules.assert_called_once()
        _vpc_mock.delete_dhcp_options.assert_called_once()
        self.assertCountEqual(
            _vpc_mock.associate_dhcp_options.mock_calls,
            [
                mock.mock.call(default=True),
                mock.mock.call([{
                    'Key': 'domain-name-servers', 'Values': [_private_ip]
                }])
            ]
        )
        self.assertEqual(ipa.subnet.instances, instances_mock)
        InstancesMock.create.assert_called_once_with(
            image='foo-123',
            name='ipa1-1000.foo.bar',
            count=1,
            subnet_id='subnet-id',
            instance_type='small',
            key_name='some-key',
            secgroup_ids=['secgroup_id'],
            user_data='user-data-script',
            role='IPA'
        )
        _vpc_mock.load_security_group_ids.assert_called_once_with(
            sg_names=['sg_common', 'ipa_secgrp']
        )
        _subnet_mock.persist.assert_called_once_with(
            cidr_block='cidr-block',
            gateway_id=123
        )

        self.assertEqual(
            IPAConfigurationMock.mock_calls[1],
            mock.mock.call(
                ipa_admin_password='ipa-admin-password',
                tm_release='release',
                hostname='ipa1-1000.foo.bar',
                vpc=_vpc_mock,
                proid='foobar'
            )
        )
        _ipa_configuration_mock.get_userdata.assert_called_once()

    @mock.patch('treadmill.infra.subnet.Subnet')
    @mock.patch('treadmill.infra.connection.Connection')
    @mock.patch('treadmill.infra.vpc.VPC')
    def test_ipa_destroy(self, VPCMock, ConnectionMock, SubnetMock):
        ConnectionMock.context.domain = 'foo.bar'
        _subnet_mock = SubnetMock(
            subnet_name='subnet-name'
        )
        _vpc_id_mock = 'vpc-id'
        _vpc_mock = VPCMock(id=_vpc_id_mock)
        _vpc_mock.secgroup_ids = ['secgroup_id']
        _instance = mock.Mock(private_ip='1.1.1.1')
        _instance.name = 'ipa'
        _subnet_mock.instances = mock.Mock(instances=[
            _instance
        ])

        ipa = IPA(
            vpc_id='vpc-id',
            name='ipa-setup'
        )
        ipa.subnet = _subnet_mock
        ipa.destroy(
            subnet_name='subnet-name'
        )
        _subnet_mock.destroy.assert_called_once_with(role='IPA')
        _vpc_mock.delete_security_groups.assert_called_once_with(
            sg_names=['ipa_secgrp']
        )
