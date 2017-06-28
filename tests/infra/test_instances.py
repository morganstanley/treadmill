"""
Unit test for EC2 instance.
"""

import unittest
import mock

from treadmill.infra.instances import Instance
from treadmill.infra.instances import Instances


class InstanceTest(unittest.TestCase):
    """Tests EC2 instance"""

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_init(self, ConnectionMock):
        conn_mock = ConnectionMock()
        instance = Instance(
            id=1,
            metadata={
                'PrivateIpAddress': '1.1.1.1',
                'Tags': [{
                    'Key': 'Name',
                    'Value': 'goo'
                }]
            }
        )

        self.assertEquals(instance.name, 'goo')
        self.assertEquals(instance.private_ip, '1.1.1.1')
        self.assertEquals(instance.ec2_conn, conn_mock)

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_create_tags(self, ConnectionMock):
        conn_mock = ConnectionMock()
        conn_mock.create_tags = mock.Mock()

        instance = Instance(
            name='foo',
            id='1',
            metadata={'AmiLaunchIndex': 100}
        )
        instance.create_tags()
        self.assertEquals(instance.name, 'foo101')

        conn_mock.create_tags.assert_called_once_with(
            Resources=['1'],
            Tags=[{
                'Key': 'Name',
                'Value': 'foo101'
            }]
        )

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_upsert_dns_record(self, ConnectionMock):
        conn_mock = ConnectionMock('route53')
        conn_mock.change_resource_record_sets = mock.Mock()

        instance = Instance(
            name='foo',
            id='1',
            metadata={'PrivateIpAddress': '10.1.2.3'}
        )
        instance.upsert_dns_record(
            hosted_zone_id='zone-id',
            domain='joo.goo'
        )
        self.assertEquals(instance.private_ip, '10.1.2.3')

        conn_mock.change_resource_record_sets.assert_called_once_with(
            HostedZoneId='zone-id',
            ChangeBatch={
                'Changes': [{
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': 'foo.joo.goo.',
                        'Type': 'A',
                        'TTL': 3600,
                        'ResourceRecords': [{
                            'Value': '10.1.2.3'
                        }]
                    }
                }]
            }
        )

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_upsert_dns_record_reverse(self, ConnectionMock):
        conn_mock = ConnectionMock('route53')
        conn_mock.change_resource_record_sets = mock.Mock()

        instance = Instance(
            name='instance-name',
            id='1',
            metadata={'PrivateIpAddress': '10.1.2.3'}
        )
        instance.upsert_dns_record(
            hosted_zone_id='reverse-zone-id',
            domain='joo.goo',
            reverse=True
        )

        conn_mock.change_resource_record_sets.assert_called_once_with(
            HostedZoneId='reverse-zone-id',
            ChangeBatch={
                'Changes': [{
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': '3.2.1.10.in-addr.arpa',
                        'Type': 'PTR',
                        'TTL': 3600,
                        'ResourceRecords': [{
                            'Value': 'instance-name.joo.goo.'
                        }]
                    }
                }]
            }
        )

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_delete_dns_record(self, ConnectionMock):
        conn_mock = ConnectionMock('route53')
        conn_mock.change_resource_record_sets = mock.Mock()

        instance = Instance(
            name='foo',
            id='1',
            metadata={'PrivateIpAddress': '10.1.2.3'}
        )
        instance.delete_dns_record(
            hosted_zone_id='zone-id',
            domain='joo.goo'
        )
        self.assertEquals(instance.private_ip, '10.1.2.3')

        conn_mock.change_resource_record_sets.assert_called_once_with(
            HostedZoneId='zone-id',
            ChangeBatch={
                'Changes': [{
                    'Action': 'DELETE',
                    'ResourceRecordSet': {
                        'Name': 'foo.joo.goo.',
                        'Type': 'A',
                        'TTL': 3600,
                        'ResourceRecords': [{
                            'Value': '10.1.2.3'
                        }]
                    }
                }]
            }
        )

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_delete_dns_record_reverse(self, ConnectionMock):
        conn_mock = ConnectionMock('route53')
        conn_mock.change_resource_record_sets = mock.Mock()

        instance = Instance(
            name='instance-name',
            id='1',
            metadata={'PrivateIpAddress': '10.1.2.3'}
        )
        instance.delete_dns_record(
            hosted_zone_id='reverse-zone-id',
            domain='joo.goo',
            reverse=True
        )

        conn_mock.change_resource_record_sets.assert_called_once_with(
            HostedZoneId='reverse-zone-id',
            ChangeBatch={
                'Changes': [{
                    'Action': 'DELETE',
                    'ResourceRecordSet': {
                        'Name': '3.2.1.10.in-addr.arpa',
                        'Type': 'PTR',
                        'TTL': 3600,
                        'ResourceRecords': [{
                            'Value': 'instance-name.joo.goo.'
                        }]
                    }
                }]
            }
        )


class InstancesTest(unittest.TestCase):
    """Tests instances collection"""

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_create(self, ConnectionMock):
        instance1_metadata_mock = {
            'InstanceId': 1,
            'AmiLaunchIndex': 999
        }
        instance2_metadata_mock = {
            'InstanceId': 2,
            'AmiLaunchIndex': 599
        }
        sample_instances = [
            {'InstanceId': 1},
            {'InstanceId': 2},
        ]
        instances_mock = [
            instance1_metadata_mock,
            instance2_metadata_mock
        ]

        conn_mock = ConnectionMock()
        conn_mock.run_instances = mock.Mock(return_value={
            'Instances': sample_instances
        })
        conn_mock.describe_instances = mock.Mock(return_value={
            'Reservations': [{'Instances': instances_mock}]
        })
        conn_mock.create_tags = mock.Mock()

        instances = Instances.create(
            key_name='key',
            name='foo',
            image_id='foo-123',
            count=2,
            instance_type='t2.small',
            subnet_id='',
            secgroup_ids=None,
            user_data='',
            hosted_zone_id='zone-id',
            reverse_hosted_zone_id='reverse-zone-id',
            domain='joo.goo'
        ).instances

        instance_ids = [i.id for i in instances]

        self.assertEquals(len(instances), 2)
        self.assertIsInstance(instances[0], Instance)
        self.assertIsInstance(instances[1], Instance)
        self.assertCountEqual(instance_ids, [1, 2])
        self.assertEquals(instances[0].metadata, instance1_metadata_mock)
        self.assertEquals(instances[1].metadata, instance2_metadata_mock)

        conn_mock.run_instances.assert_called_with(
            ImageId='foo-123',
            InstanceType='t2.small',
            KeyName='key',
            MaxCount=2,
            MinCount=2,
            SecurityGroupIds=None,
            SubnetId='',
            UserData='',
        )
        conn_mock.describe_instances.assert_called_with(
            InstanceIds=[1, 2]
        )
        self.assertCountEqual(
            conn_mock.change_resource_record_sets.mock_calls,
            [
                mock.mock.call(
                    ChangeBatch={
                        'Changes': [{
                            'ResourceRecordSet': {
                                'ResourceRecords': [{
                                    'Value': ''
                                }],
                                'Name': 'foo1000.joo.goo.',
                                'TTL': 3600,
                                'Type': 'A'
                            },
                            'Action': 'UPSERT'
                        }]
                    },
                    HostedZoneId='zone-id'
                ),
                mock.mock.call(
                    ChangeBatch={
                        'Changes': [{
                            'ResourceRecordSet': {
                                'ResourceRecords': [{
                                    'Value': 'foo1000.joo.goo.'
                                }],
                                'Name': '.in-addr.arpa',
                                'TTL': 3600,
                                'Type': 'PTR'
                            },
                            'Action': 'UPSERT'
                        }]
                    },
                    HostedZoneId='reverse-zone-id'
                ),
                mock.mock.call(
                    ChangeBatch={
                        'Changes': [{
                            'ResourceRecordSet': {
                                'ResourceRecords': [{
                                    'Value': ''
                                }],
                                'Name': 'foo600.joo.goo.',
                                'TTL': 3600,
                                'Type': 'A'
                            },
                            'Action': 'UPSERT'
                        }]
                    },
                    HostedZoneId='zone-id'
                ),
                mock.mock.call(
                    ChangeBatch={
                        'Changes': [{
                            'ResourceRecordSet': {
                                'ResourceRecords': [{
                                    'Value': 'foo600.joo.goo.'
                                }],
                                'Name': '.in-addr.arpa',
                                'TTL': 3600,
                                'Type': 'PTR'
                            },
                            'Action': 'UPSERT'
                        }]
                    },
                    HostedZoneId='reverse-zone-id'
                )
            ]
        )
        self.assertCountEqual(
            conn_mock.create_tags.mock_calls,
            [
                mock.mock.call(
                    Resources=[1],
                    Tags=[{
                        'Key': 'Name',
                        'Value': 'foo1000'
                    }]
                ),
                mock.mock.call(
                    Resources=[2],
                    Tags=[{
                        'Key': 'Name',
                        'Value': 'foo600'
                    }]
                )

            ]
        )

    @mock.patch('treadmill.infra.instances.Instance')
    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_terminate(self, ConnectionMock, InstanceMock):
        conn_mock = ConnectionMock()

        instance_1_mock = InstanceMock()
        instance_1_mock.id = 1
        instance = Instances(instances=[instance_1_mock])
        instance.volume_ids = ['vol-id0']

        instance.terminate('zone-id', 'reverse-zone-id', 'tw.treadmill.test')

        conn_mock.describe_instance_status.assert_called()
        self.assertCountEqual(
            instance_1_mock.delete_dns_record.mock_calls,
            [
                mock.mock.call(
                    'zone-id',
                    'tw.treadmill.test'
                ),
                mock.mock.call(
                    reverse=True,
                    domain='tw.treadmill.test',
                    hosted_zone_id='reverse-zone-id'
                )
            ]

        )
        conn_mock.terminate_instances.assert_called_once_with(
            InstanceIds=[1]
        )
        self.assertCountEqual(
            conn_mock.delete_volume.mock_calls,
            [
                mock.mock.call(VolumeId='vol-id0'),
            ]
        )

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_get_volume_ids(self, connectionMock):
        conn_mock = connectionMock()
        conn_mock.describe_volumes = mock.Mock(return_value={
            'Volumes': [{
                'VolumeId': 'vol-id'
            }]
        })

        instance = Instances([Instance(id=1)])
        instance.get_volume_ids()

        self.assertEquals(instance.volume_ids, ['vol-id'])
        conn_mock.describe_volumes.assert_called_once_with(
            Filters=[{
                'Name': 'attachment.instance-id',
                'Values': [1]
            }]
        )

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_load_json_without_criteria(self, ConnectionMock):
        conn_mock = ConnectionMock()

        self.assertEqual(Instances.load_json(), [])

        conn_mock.describe_instances.assert_not_called()

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_load_json_with_instance_ids(self, ConnectionMock):
        conn_mock = ConnectionMock()

        sample_instances = [
            {'InstanceId': 1}, {'InstanceId': 2}, {'InstanceId': 3}
        ]
        conn_mock.describe_instances = mock.Mock(return_value={
            'Reservations': [{'Instances': sample_instances}]
        })

        instance_details = Instances.load_json([1, 2, 3])

        conn_mock.describe_instances.assert_called_once_with(
            InstanceIds=[1, 2, 3]
        )
        self.assertEquals(instance_details, sample_instances)

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_load_json_with_filters(self, ConnectionMock):
        conn_mock = ConnectionMock()

        sample_instances = [
            {'InstanceId': 1}, {'InstanceId': 2}, {'InstanceId': 3}
        ]
        conn_mock.describe_instances = mock.Mock(return_value={
            'Reservations': [{'Instances': sample_instances}]
        })

        instance_details = Instances.load_json(filters=[{'foo': 'bar'}])

        conn_mock.describe_instances.assert_called_once_with(
            Filters=[{'foo': 'bar'}]
        )
        self.assertEquals(instance_details, sample_instances)


if __name__ == '__main__':
    unittest.main()
