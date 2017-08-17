"""
Unit test for EC2 node.
"""

import unittest
import mock

from treadmill.infra.setup.node import Node


class NodeTest(unittest.TestCase):
    """Tests EC2 Node"""

    @mock.patch('treadmill.infra.instances.Instances')
    @mock.patch('treadmill.infra.connection.Connection')
    @mock.patch('treadmill.infra.vpc.VPC')
    def test_node_destroy_by_instance_id(self, VPCMock,
                                         ConnectionMock, InstancesMock):
        _instances_obj_mock = mock.Mock()
        InstancesMock.get = mock.Mock(return_value=_instances_obj_mock)
        vpc_mock = VPCMock(
            id='vpc-id',
        )
        vpc_mock.load_hosted_zone_ids = mock.Mock()
        vpc_mock.hosted_zone_id = 'hosted-zone-id'
        vpc_mock.reverse_hosted_zone_id = 'reverse-hosted-zone-id'

        node = Node(
            vpc_id='vpc-id',
            name='node'
        )
        node.destroy(
            instance_id='instance-id'
        )

        vpc_mock.load_hosted_zone_ids.assert_called_once()
        InstancesMock.get.assert_called_once_with(ids=['instance-id'])
        _instances_obj_mock.terminate.assert_called_once_with(
            hosted_zone_id='hosted-zone-id',
            reverse_hosted_zone_id='reverse-hosted-zone-id',
        )

    @mock.patch('treadmill.infra.instances.Instances')
    @mock.patch('treadmill.infra.connection.Connection')
    @mock.patch('treadmill.infra.vpc.VPC')
    def test_node_destroy_by_instance_name(self, VPCMock,
                                           ConnectionMock, InstancesMock):
        _instances_obj_mock = mock.Mock()
        InstancesMock.get = mock.Mock(return_value=_instances_obj_mock)
        vpc_mock = VPCMock(
            id='vpc-id',
        )
        vpc_mock.load_hosted_zone_ids = mock.Mock()
        vpc_mock.hosted_zone_id = 'hosted-zone-id'
        vpc_mock.reverse_hosted_zone_id = 'reverse-hosted-zone-id'

        node = Node(
            vpc_id='vpc-id',
            name='node-instance-name'
        )
        node.destroy()

        vpc_mock.load_hosted_zone_ids.assert_called_once()
        InstancesMock.get.assert_called_once_with(
            filters=[
                {
                    'Name': 'tag-key',
                    'Values': ['Name']
                },
                {
                    'Name': 'tag-value',
                    'Values': ['node-instance-name']
                },
            ]
        )
        _instances_obj_mock.terminate.assert_called_once_with(
            hosted_zone_id='hosted-zone-id',
            reverse_hosted_zone_id='reverse-hosted-zone-id',
        )

    @mock.patch('treadmill.infra.instances.Instances')
    @mock.patch('treadmill.infra.connection.Connection')
    @mock.patch('treadmill.infra.vpc.VPC')
    def test_node_destroy_without_identifier_should_do_nothing(
            self,
            VPCMock,
            ConnectionMock,
            InstancesMock
    ):
        InstancesMock.get = mock.Mock()
        vpc_mock = VPCMock()
        vpc_mock.load_hosted_zone_ids = mock.Mock()

        node = Node(
            vpc_id='vpc-id',
            name=None
        )
        node.destroy()

        vpc_mock.load_hosted_zone_ids.assert_not_called()
        InstancesMock.get.assert_not_called()
