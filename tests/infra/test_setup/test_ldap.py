"""
Unit test for EC2 ldap.
"""

import unittest
import mock

from treadmill.infra.setup.ldap import LDAP
from treadmill.infra.setup.base_provision import BaseProvision
from treadmill.infra import exceptions


class LDAPTest(unittest.TestCase):
    """Tests EC2 LDAP"""

    @mock.patch.object(BaseProvision,
                       'hostnames_for',
                       mock.Mock(return_value=[None]))
    @mock.patch('treadmill.infra.connection.Connection',
                mock.Mock())
    def test_setup_ldap_no_ipa(self):
        ldap = LDAP(
            name='ldap',
            vpc_id='vpc-id',
        )

        with self.assertRaises(exceptions.IPAServerNotFound) as err:
            ldap.setup(
                image='foo-123',
                count=1,
                cidr_block='cidr-block',
                key='some-key',
                instance_type='small',
                tm_release='release',
                app_root='app-root',
                ipa_admin_password='ipa_pass',
                proid='foobar',
                subnet_name='sub-name'
            )

        self.assertEqual(
            err.exception.message,
            'Please check if IPA Server is up and running.'
        )

    @mock.patch('time.time', mock.Mock(return_value=1000))
    @mock.patch('treadmill.infra.subnet.Subnet')
    @mock.patch('treadmill.api.ipa.API')
    @mock.patch('treadmill.infra.configuration.LDAP')
    @mock.patch('treadmill.infra.connection.Connection')
    @mock.patch('treadmill.infra.vpc.VPC')
    @mock.patch('treadmill.infra.instances.Instances')
    def test_setup_ldap(self, InstancesMock, VPCMock,
                        ConnectionMock, LDAPConfigurationMock,
                        IpaAPIMock, SubnetMock):
        ConnectionMock.context.domain = 'domain'
        _ipa_api_mock = IpaAPIMock()
        _ipa_api_mock.add_host = mock.Mock(return_value='otp')
        InstancesMock.get_hostnames_by_roles = mock.Mock(return_value={
            'IPA': 'ipa-hostname'
        })
        instance_mock = mock.Mock(private_ip='1.1.1.1')
        instances_mock = mock.Mock(instances=[instance_mock])
        InstancesMock.create = mock.Mock(return_value=instances_mock)
        _vpc_id_mock = 'vpc-id'
        _vpc_mock = VPCMock(id=_vpc_id_mock)
        _vpc_mock.gateway_ids = [123]
        _vpc_mock.secgroup_ids = ['secgroup-id']
        _subnet_mock = mock.Mock(
            name='subnet-name',
            id='subnet-id',
            vpc_id=_vpc_id_mock,
            persisted=False
        )
        SubnetMock.get = mock.Mock(return_value=_subnet_mock)
        _ldap_configuration_mock = LDAPConfigurationMock()
        _ldap_configuration_mock.get_userdata = mock.Mock(
            return_value='user-data-script'
        )
        ldap = LDAP(
            name='ldap',
            vpc_id=_vpc_id_mock,
        )
        ldap.subnet_name = 'ldap-subnet-name'
        ldap.setup(
            image='foo-123',
            count=1,
            cidr_block='cidr-block',
            key='some-key',
            instance_type='small',
            tm_release='release',
            app_root='app-root',
            ipa_admin_password='ipa_pass',
            proid='foobar',
            subnet_name='sub-name'
        )

        self.assertEqual(ldap.subnet.instances, instances_mock)
        _ipa_api_mock.add_host.assert_called_with(
            hostname='ldap1-1000.domain'
        )
        _ipa_api_mock.service_add.assert_called_with(
            'ldap',
            'ldap1-1000.domain',
            {
                'domain': 'domain',
                'hostname': 'ldap1-1000.domain'
            }
        )
        InstancesMock.get_hostnames_by_roles.assert_called_with(
            vpc_id=mock.ANY,
            roles=['IPA']
        )
        InstancesMock.create.assert_called_once_with(
            image='foo-123',
            name='ldap1-1000.domain',
            count=1,
            subnet_id='subnet-id',
            instance_type='small',
            secgroup_ids=['secgroup-id'],
            key_name='some-key',
            user_data='user-data-script',
            role='LDAP',
        )
        _vpc_mock.load_security_group_ids.assert_called_once_with(
            sg_names=['sg_common']
        )
        _subnet_mock.persist.assert_called_once_with(
            cidr_block='cidr-block',
            gateway_id=123
        )

        self.assertEqual(
            LDAPConfigurationMock.mock_calls[1],
            mock.mock.call(
                hostname='ldap1-1000.domain',
                otp='otp',
                tm_release='release',
                app_root='app-root',
                ipa_admin_password='ipa_pass',
                ipa_server_hostname='ipa-hostname',
                proid='foobar',
            )
        )
        _ldap_configuration_mock.get_userdata.assert_called_once()

    @mock.patch('treadmill.infra.subnet.Subnet')
    @mock.patch('treadmill.infra.connection.Connection')
    @mock.patch('treadmill.infra.vpc.VPC')
    @mock.patch('treadmill.infra.instances.Instances')
    def test_ldap_destroy(self, InstancesMock, VPCMock, ConnectionMock,
                          SubnetMock):
        _subnet_mock = SubnetMock(name='subnet-name')
        _subnet_mock.instances = mock.Mock(instances=[
            mock.Mock(private_ip='1.1.1.1')
        ])

        InstancesMock.get_hostnames_by_roles = mock.Mock(return_value={
            'LDAP': 'ldap1-1000.domain'
        })

        ldap = LDAP(
            vpc_id='vpc-id',
            name='ldap'
        )
        ldap.destroy(
            subnet_name='subnet-name'
        )
        _subnet_mock.destroy.assert_called_once_with(role='LDAP')
