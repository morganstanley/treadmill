"""
Unit test for EC2 instance.
"""

import unittest
import mock

from treadmill.infra.instances import Instance
from treadmill.infra.instances import Instances


class InstanceTest(unittest.TestCase):
    """Tests EC2 instance"""

    def test_init(self):
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

    @mock.patch('treadmill.infra.connection.Connection')
    def test_create_tags(self, ConnectionMock):
        conn_mock = ConnectionMock()
        conn_mock.create_tags = mock.Mock()
        Instance.ec2_conn = conn_mock

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
    def test_create_tags_with_role(self, ConnectionMock):
        ConnectionMock.context.domain = 'do.main'
        conn_mock = ConnectionMock()
        conn_mock.create_tags = mock.Mock()
        Instance.ec2_conn = conn_mock
        instance = Instance(
            name='foo',
            id='1',
            metadata={'AmiLaunchIndex': 100},
            role='role-name'
        )
        instance.create_tags()
        self.assertEquals(instance.name, 'foo101')
        self.assertEquals(instance.hostname, 'foo101.do.main')

        conn_mock.create_tags.assert_called_once_with(
            Resources=['1'],
            Tags=[{
                'Key': 'Name',
                'Value': 'foo101'
            }, {
                'Key': 'Role',
                'Value': 'role-name'
            }]
        )

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_create_tags_with_node_role(self, ConnectionMock):
        ConnectionMock.context.domain = 'do.main'
        conn_mock = ConnectionMock()
        conn_mock.create_tags = mock.Mock()
        Instance.ec2_conn = conn_mock

        instance = Instance(
            name='Foo',
            id='instanceid',
            metadata={'AmiLaunchIndex': 100},
            role='NODE'
        )
        instance.create_tags()
        self.assertEquals(instance.name, 'Foo101-instanceid')
        self.assertEquals(instance.hostname, 'foo101-instanceid.do.main')

        conn_mock.create_tags.assert_called_once_with(
            Resources=['instanceid'],
            Tags=[{
                'Key': 'Name',
                'Value': 'Foo101-instanceid'
            }, {
                'Key': 'Role',
                'Value': 'NODE'
            }]
        )


class InstancesTest(unittest.TestCase):
    """Tests instances collection"""

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_create(self, ConnectionMock):
        ConnectionMock.context.domain = 'joo.goo'
        instance1_metadata_mock = {
            'InstanceId': 1,
            'AmiLaunchIndex': 0
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
        conn_mock.describe_images = mock.Mock(return_value={
            'Images': [{'ImageId': 'ami-123'}]
        })
        Instance.ec2_conn = Instance.route53_conn = conn_mock

        instances = Instances.create(
            key_name='key',
            name='foo',
            image='foo-123',
            count=2,
            instance_type='t2.small',
            subnet_id='',
            secgroup_ids=None,
            user_data='',
            role='role'
        ).instances

        instance_ids = [i.id for i in instances]

        self.assertEquals(len(instances), 2)
        self.assertIsInstance(instances[0], Instance)
        self.assertIsInstance(instances[1], Instance)
        self.assertCountEqual(instance_ids, [1, 2])
        self.assertEquals(instances[0].metadata, instance1_metadata_mock)
        self.assertEquals(instances[1].metadata, instance2_metadata_mock)
        self.assertEquals(instances[0].role, 'role')
        self.assertEquals(instances[1].role, 'role')

        conn_mock.run_instances.assert_called_with(
            ImageId='ami-123',
            InstanceType='t2.small',
            KeyName='key',
            MaxCount=2,
            MinCount=2,
            NetworkInterfaces=[{
                'Groups': None,
                'AssociatePublicIpAddress': True,
                'SubnetId': '',
                'DeviceIndex': 0
            }],
            UserData='',
        )
        conn_mock.describe_instances.assert_called_with(
            InstanceIds=[1, 2]
        )

    @mock.patch('treadmill.infra.instances.Instance')
    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_terminate(self, ConnectionMock, InstanceMock):
        conn_mock = ConnectionMock()

        instance_1_mock = InstanceMock()
        instance_1_mock.id = 1
        instance = Instances(instances=[instance_1_mock])
        instance.volume_ids = ['vol-id0']

        Instance.ec2_conn = conn_mock
        instance.terminate()

        conn_mock.describe_instance_status.assert_called()
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
    def test_load_volume_ids(self, connectionMock):
        conn_mock = connectionMock()
        conn_mock.describe_volumes = mock.Mock(return_value={
            'Volumes': [{
                'VolumeId': 'vol-id'
            }]
        })

        Instance.ec2_conn = conn_mock
        instance = Instances([Instance(id=1)])
        instance.load_volume_ids()

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

        Instance.ec2_conn = conn_mock
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
        Instance.ec2_conn = conn_mock

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
        Instance.ec2_conn = conn_mock

        instance_details = Instances.load_json(filters=[{'foo': 'bar'}])

        conn_mock.describe_instances.assert_called_once_with(
            Filters=[{'foo': 'bar'}]
        )
        self.assertEquals(instance_details, sample_instances)

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_get_ami_id(self, ConnectionMock):
        conn_mock = ConnectionMock()

        sample_images = [
            {'ImageId': 'ami-123', 'CreationDate': '2017-08-23T00:00:00.000Z'},
            {'ImageId': 'ami-456', 'CreationDate': '2016-08-23T00:00:00.000Z'}
        ]

        conn_mock.describe_images = mock.Mock(return_value={
            'Images': sample_images
        })
        Instance.ec2_conn = conn_mock

        ami_id = Instances.get_ami_id('foo-bar')

        conn_mock.describe_images.assert_called_once_with(
            Filters=[
                {'Name': 'name', 'Values': ['foo-bar*']},
                {'Name': 'owner-id', 'Values': ['309956199498']},
                {'Name': 'image-type', 'Values': ['machine']}
            ]
        )
        self.assertEquals(ami_id, 'ami-123')


if __name__ == '__main__':
    unittest.main()
