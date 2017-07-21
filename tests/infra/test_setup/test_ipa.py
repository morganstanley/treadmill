"""
Unit test for EC2 ipa.
"""

import unittest
import mock

from treadmill.infra.setup.ipa import IPA


class IPATest(unittest.TestCase):
    """Tests EC2 ipa setup."""

    @mock.patch('treadmill.infra.configuration.IPA')
    @mock.patch('treadmill.infra.connection.Connection')
    @mock.patch('treadmill.infra.vpc.VPC')
    @mock.patch('treadmill.infra.instances.Instances')
    def test_setup_ipa(self, InstancesMock,
                       VPCMock, ConnectionMock, IPAConfigurationMock):
        ConnectionMock.context.domain = 'foo.bar'
        instance_mock = mock.Mock(private_ip='1.1.1.1')
        instance_mock.name = 'ipa'
        instances_mock = mock.Mock(instances=[instance_mock])
        InstancesMock.create = mock.Mock(return_value=instances_mock)
        conn_mock = ConnectionMock('route53')
        _vpc_id_mock = 'vpc-id'
        _vpc_mock = VPCMock(id=_vpc_id_mock)
        _vpc_mock.hosted_zone_id = 'hosted-zone-id'
        _vpc_mock.reverse_hosted_zone_id = 'reverse-hosted-zone-id'
        _vpc_mock.secgroup_ids = ['secgroup_id']
        _vpc_mock.gateway_ids = [123]
        _vpc_mock.subnets = [mock.Mock(id='subnet-id')]
        _ipa_configuration_mock = IPAConfigurationMock()
        _ipa_configuration_mock.get_userdata = mock.Mock(
            return_value='user-data-script'
        )
        ipa = IPA(
            name='ipa',
            vpc_id=_vpc_id_mock,
        )
        ipa.setup(
            image_id='foo-123',
            count=1,
            cidr_block='cidr-block',
            key='some-key',
            tm_release='release',
            ipa_admin_password='ipa-admin-password',
            instance_type='small'
        )

        self.assertEqual(ipa.subnet.instances, instances_mock)
        InstancesMock.create.assert_called_once_with(
            image_id='foo-123',
            name='ipa',
            count=1,
            subnet_id='subnet-id',
            instance_type='small',
            key_name='some-key',
            secgroup_ids=['secgroup_id'],
            user_data='user-data-script',
            hosted_zone_id='hosted-zone-id',
            reverse_hosted_zone_id='reverse-hosted-zone-id',
            role='IPA'
        )
        _vpc_mock.load_hosted_zone_ids.assert_called_once()
        _vpc_mock.load_security_group_ids.assert_called_once()
        _vpc_mock.create_subnet.assert_called_once_with(
            cidr_block='cidr-block',
            name='ipa',
            gateway_id=123
        )

        self.assertEqual(
            IPAConfigurationMock.mock_calls[1],
            mock.mock.call(
                ipa_admin_password='ipa-admin-password',
                tm_release='release',
                cell=None,
                name='ipa'
            )
        )
        _ipa_configuration_mock.get_userdata.assert_called_once()

        expected_calls = [
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': '_kerberos-master._tcp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 88 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': '_kerberos-master._udp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 88 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': '_kerberos._tcp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 88 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': '_kerberos._udp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 88 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': '_kpasswd._tcp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 464 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': '_kpasswd._udp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 464 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': '_ldap._tcp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 389 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': '_ntp._udp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 123 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': 'ipa-ca.foo.bar.',
                            'Type': 'A',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '1.1.1.1'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': '_kerberos.foo.bar.',
                            'Type': 'TXT',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '"FOO.BAR"'
                            }]
                        }
                    }]
                }
            )
        ]
        self.assertCountEqual(
            conn_mock.change_resource_record_sets.mock_calls,
            expected_calls
        )

    @mock.patch('treadmill.infra.subnet.Subnet')
    @mock.patch('treadmill.infra.connection.Connection')
    @mock.patch('treadmill.infra.vpc.VPC')
    def test_ipa_destroy(self, VPCMock, ConnectionMock, SubnetMock):
        ConnectionMock.context.domain = 'foo.bar'
        conn_mock = ConnectionMock('route53')
        _subnet_mock = SubnetMock(
            id='subnet-id'
        )
        _instance = mock.Mock(private_ip='1.1.1.1')
        _instance.name = 'ipa'
        _subnet_mock.instances = mock.Mock(instances=[
            _instance
        ])

        vpc_mock = VPCMock(
            id='vpc-id',
        )
        vpc_mock.load_hosted_zone_ids = mock.Mock()
        vpc_mock.hosted_zone_id = 'hosted-zone-id'
        vpc_mock.reverse_hosted_zone_id = 'reverse-hosted-zone-id'
        ipa = IPA(
            vpc_id='vpc-id',
            name='ipa-setup'
        )
        ipa.subnet = _subnet_mock
        ipa.destroy(
            subnet_id='subnet-id'
        )

        vpc_mock.load_hosted_zone_ids.assert_called_once()
        _subnet_mock.destroy.assert_called_once_with(
            hosted_zone_id='hosted-zone-id',
            reverse_hosted_zone_id='reverse-hosted-zone-id',
            role='IPA'
        )
        expected_calls = [
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': '_kerberos-master._tcp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 88 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': '_kerberos-master._udp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 88 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': '_kerberos._tcp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 88 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': '_kerberos._udp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 88 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': '_kpasswd._tcp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 464 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': '_kpasswd._udp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 464 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': '_ldap._tcp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 389 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': '_ntp._udp.foo.bar.',
                            'Type': 'SRV',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '0 100 123 ipa.foo.bar.'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': 'ipa-ca.foo.bar.',
                            'Type': 'A',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '1.1.1.1'
                            }]
                        }
                    }]
                }
            ),
            mock.mock.call(
                HostedZoneId='hosted-zone-id',
                ChangeBatch={
                    'Changes': [{
                        'Action': 'DELETE',
                        'ResourceRecordSet': {
                            'Name': '_kerberos.foo.bar.',
                            'Type': 'TXT',
                            'TTL': 86400,
                            'ResourceRecords': [{
                                'Value': '"FOO.BAR"'
                            }]
                        }
                    }]
                }
            )
        ]
        self.assertCountEqual(
            conn_mock.change_resource_record_sets.mock_calls,
            expected_calls
        )
