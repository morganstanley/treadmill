"""
Unit test for EC2 node setup.
"""

import unittest
import mock

from treadmill.infra.setup.node import Node


class NodeTest(unittest.TestCase):
    """Tests EC2 node setup."""

    @mock.patch('treadmill.infra.setup.node.instances.Instances')
    def test_setup_node(self, InstancesMock):
        instances_mock = InstancesMock()
        instances_mock.instances = 'foo'

        node = Node()
        node.setup(name='node', image_id='foo-123', count=1, subnet_id='123',
                   secgroup_ids=[1, 2])

        self.assertIsNotNone(node.instances)

    @mock.patch('treadmill.infra.setup.node.instances.Instances')
    def test_setup_terminate(self, InstancesMock):
        node = Node()
        node.instances = InstancesMock()
        node.terminate()

        node.instances.terminate.assert_called_once()
