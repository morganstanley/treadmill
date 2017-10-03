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
        self.assertEquals(instance.name, 'foo')

        conn_mock.create_tags.assert_called_once_with(
            Resources=['1'],
            Tags=[{
                'Key': 'Name',
                'Value': 'foo'
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
        self.assertEquals(instance.name, 'foo')

        conn_mock.create_tags.assert_called_once_with(
            Resources=['1'],
            Tags=[{
                'Key': 'Name',
                'Value': 'foo'
            }, {
                'Key': 'Role',
                'Value': 'role-name'
            }]
        )

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_running_instance(self, ConnectionMock):
        conn_mock = ConnectionMock()
        conn_mock.describe_instance_status = mock.Mock(
            return_value={
                'InstanceStatuses': [{
                    'InstanceStatus': {
                        'Details': [{
                            'Status': 'goo'
                        }]
                    }
                }]
            }
        )
        _instance = Instance(
            name='foo',
            metadata={'InstanceId': 'instance-id'}
        )
        _instance.ec2_conn = conn_mock
        self.assertEqual(
            _instance.running_status(),
            'goo'
        )
        conn_mock.describe_instance_status.assert_called_once_with(
            InstanceIds=['instance-id']
        )

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_running_instance_without_refresh(self, ConnectionMock):
        conn_mock = ConnectionMock()
        _instance = Instance(
            name='foo'
        )
        _instance.ec2_conn = conn_mock
        _instance._running_status = 'goo'
        self.assertEqual(
            _instance.running_status(),
            'goo'
        )
        conn_mock.describe_instance_status.assert_not_called()

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_running_instance_with_refresh(self, ConnectionMock):
        conn_mock = ConnectionMock()
        conn_mock.describe_instance_status = mock.Mock(
            return_value={
                'InstanceStatuses': [{
                    'InstanceStatus': {
                        'Details': [{
                            'Status': 'new-goo'
                        }]
                    }
                }]
            }
        )
        _instance = Instance(
            name='foo',
            metadata={'InstanceId': 'instance-id'}
        )
        _instance.ec2_conn = conn_mock
        _instance._running_status = 'goo'
        self.assertEqual(
            _instance.running_status(),
            'goo'
        )
        self.assertEqual(
            _instance.running_status(refresh=True),
            'new-goo'
        )
        conn_mock.describe_instance_status.assert_called_once_with(
            InstanceIds=['instance-id']
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
            IamInstanceProfile={}
        )
        conn_mock.describe_instances.assert_called_with(
            InstanceIds=[1, 2]
        )

    @mock.patch('treadmill.api.ipa.API')
    @mock.patch('treadmill.infra.instances.Instance')
    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_terminate(self, ConnectionMock, InstanceMock, IpaAPIMock):
        conn_mock = ConnectionMock()
        ipa_api_mock = IpaAPIMock()
        instance_1_mock = InstanceMock()
        instance_1_mock.id = 1
        instance_1_mock.hostname = 'hostname'
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
        ipa_api_mock.delete_host.assert_called_once_with(hostname='hostname')

    @mock.patch('treadmill.api.ipa.API')
    @mock.patch('treadmill.infra.instances.Instance')
    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_terminate_ipa(self, ConnectionMock, InstanceMock, IpaAPIMock):
        conn_mock = ConnectionMock()
        ipa_api_mock = IpaAPIMock()
        instance_1_mock = InstanceMock()
        instance_1_mock.id = 1
        instance_1_mock.role = 'IPA'
        instance_1_mock.hostname = 'hostname'
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
        ipa_api_mock.delete_host.assert_not_called()

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
    def test_get_by_roles(self, ConnectionMock):
        conn_mock = ConnectionMock()

        sample_instances = [
            {'InstanceId': 1}
        ]
        conn_mock.describe_instances = mock.Mock(return_value={
            'Reservations': [{'Instances': sample_instances}]
        })
        Instance.ec2_conn = conn_mock

        result = Instances.get_by_roles(vpc_id='vpc-id', roles=['IPA'])

        conn_mock.describe_instances.assert_called_once_with(
            Filters=[
                {'Name': 'vpc-id', 'Values': ['vpc-id']},
                {'Name': 'tag-key', 'Values': ['Role']},
                {'Name': 'tag-value', 'Values': ['IPA']}
            ]
        )
        self.assertIsInstance(result, Instances)
        self.assertEquals(result.instances[0].metadata, sample_instances[0])

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_get_by_roles_no_instance(self, ConnectionMock):
        conn_mock = ConnectionMock()

        conn_mock.describe_instances = mock.Mock(return_value={
            'Reservations': [{'Instances': []}]
        })
        Instance.ec2_conn = conn_mock

        result = Instances.get_by_roles(vpc_id='vpc-id', roles=['IPA'])

        conn_mock.describe_instances.assert_called_once_with(
            Filters=[
                {'Name': 'vpc-id', 'Values': ['vpc-id']},
                {'Name': 'tag-key', 'Values': ['Role']},
                {'Name': 'tag-value', 'Values': ['IPA']}
            ]
        )

        self.assertIsInstance(result, Instances)
        self.assertEqual(result.instances, [])

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_hostnames_by_roles_with_multiple_instances(self, ConnectionMock):
        ConnectionMock.context.domain = 'domain'
        conn_mock = ConnectionMock()
        sample_instances = [
            {
                'InstanceId': 1, 'Tags': [
                    {'Key': 'Name', 'Value': 'ipa-hostname-with-domain'},
                    {'Key': 'Role', 'Value': 'IPA'}
                ]
            }, {
                'InstanceId': 2, 'Tags': [
                    {'Key': 'Name', 'Value': 'ipa2-hostname-with-domain'},
                    {'Key': 'Role', 'Value': 'IPA'}
                ]
            }
        ]
        conn_mock.describe_instances = mock.Mock(return_value={
            'Reservations': [{'Instances': sample_instances}]
        })
        Instance.ec2_conn = conn_mock

        result = Instances.get_hostnames_by_roles(
            vpc_id='vpc-id', roles=['IPA']
        )

        conn_mock.describe_instances.assert_called_once_with(
            Filters=[
                {'Name': 'vpc-id', 'Values': ['vpc-id']},
                {'Name': 'tag-key', 'Values': ['Role']},
                {'Name': 'tag-value', 'Values': ['IPA']}
            ]
        )
        self.assertEquals(result, {
            'IPA': 'ipa-hostname-with-domain,ipa2-hostname-with-domain'
        })

    @mock.patch('treadmill.infra.instances.connection.Connection')
    def test_hostnames_by_roles_with_single_instances(self, ConnectionMock):
        ConnectionMock.context.domain = 'domain'
        conn_mock = ConnectionMock()
        sample_instances = [
            {
                'InstanceId': 1, 'Tags': [
                    {'Key': 'Name', 'Value': 'ipa-hostname-with-domain'},
                    {'Key': 'Role', 'Value': 'IPA'}
                ]
            }
        ]
        conn_mock.describe_instances = mock.Mock(return_value={
            'Reservations': [{'Instances': sample_instances}]
        })
        Instance.ec2_conn = conn_mock

        result = Instances.get_hostnames_by_roles(
            vpc_id='vpc-id', roles=['IPA']
        )

        conn_mock.describe_instances.assert_called_once_with(
            Filters=[
                {'Name': 'vpc-id', 'Values': ['vpc-id']},
                {'Name': 'tag-key', 'Values': ['Role']},
                {'Name': 'tag-value', 'Values': ['IPA']}
            ]
        )
        self.assertEquals(result, {
            'IPA': 'ipa-hostname-with-domain'
        })

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
