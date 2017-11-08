"""
Unit test for EC2 zookeeper.
"""

import unittest
import mock

from treadmill.infra.setup import zookeeper


class ZookeeperTest(unittest.TestCase):
    """Tests EC2 zookeeper setup."""

    @mock.patch('treadmill.infra.connection.Connection')
    def test_constuct_cfg_data(self, ConnectionMock):
        zk = zookeeper.Zookeeper(
            vpc_id='something',
            name='something'
        )
        _hostnames = {
            '1': 'zk1-hostname',
            '2': 'zk2-hostname',
            '3': 'zk3-hostname',
        }
        result = zk._construct_cfg_data(_hostnames)
        expected_cfg_data = """server.1=zk1-hostname:2888:3888
server.2=zk2-hostname:2888:3888
server.3=zk3-hostname:2888:3888"""

        self.assertEqual(
            result,
            expected_cfg_data
        )
