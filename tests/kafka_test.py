"""Unit test for Kafka API, i.e. treadmill.kafka.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import unittest

import mock

from treadmill import context
from treadmill import kafka

_ZKURL = 'zookeeper://foo@bar.xx.com,baz.xx.com'


class KafkaTest(unittest.TestCase):
    """Tests for teadmill.kafka."""

    def setUp(self):
        """Setup test"""
        context.GLOBAL.cell = 'test'
        context.GLOBAL.zk.url = 'zookeeper://xxx@yyy:123'
        context.GLOBAL.ldap.url = 'ldap://xxx@yyy:123'

        self.zkclient_mock = mock.Mock()
        self.zkclient_mock.get_children = mock.MagicMock(
            return_value=['foo.kafka.1', 'foo.bar'])
        context.ZkContext.conn = self.zkclient_mock

        self.ldap_mock = mock.Mock()
        context.AdminContext.conn = self.ldap_mock

    def tearDown(self):
        """Tear down test"""
        pass

    def test_log_dir(self):
        """Test LOG_DIR is set"""
        self.assertIsNotNone(kafka.log_dir('LOG_DIR'))

    def test_app_log(self):
        """Test APP_LOG is set"""
        self.assertIsNotNone(kafka.app_log('APP_LOG'))

    def test_data_dir(self):
        """Test DATA_DIR is set"""
        self.assertIsNotNone(kafka.data_dir('DATA_DIR'))

    def test_setup_env(self):
        """Test setup_env is set and with correct default data"""
        kafka_env = kafka.setup_env()

        self.assertIsNotNone(kafka_env.get('LOG_DIR'))
        self.assertIsNotNone(kafka_env.get('APP_LOG'))

        self.assertTrue(os.path.isdir(kafka_env.get('LOG_DIR')))

        # Check data_dir option, this also makes sure mkdir_safe doesn't throw
        kafka_env = kafka.setup_env(with_data_dir=True)

        self.assertIsNotNone(kafka_env.get('DATA_DIR'))
        self.assertTrue(os.path.isdir(kafka_env.get('DATA_DIR')))

    def test_zk_instances_by_zkurl(self):
        """Test getting Zookeeper instances for Kafka by ZK URL"""
        zk_instances = kafka.zk_instances_by_zkurl(_ZKURL)

        self.assertEqual(
            zk_instances,
            'bar.xx.com,baz.xx.com/%s' % kafka.KAFKA_ZK_ROOT
        )

    @mock.patch('treadmill.kafka._is_broker_up',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.admin.Application.list',
                mock.Mock(return_value=[{'_id': 'proid.app1'},
                                        {'_id': 'proid.app2'}]))
    def test_get_replica(self):
        """Test getting the number of Kafka replicas"""
        replica = kafka.get_replica(['foo:1111'])

        self.assertEqual(replica, 1)

    @mock.patch('treadmill.kafka.get_master_brokers',
                mock.Mock(return_value=['foo:1111']))
    @mock.patch('treadmill.kafka._is_broker_up',
                mock.Mock(return_value=True))
    def test_get_brokers_with_masters(self):
        """Test getting the number of Kafka brokers with masters"""
        brokers = kafka.get_brokers('test', 'tm.xxx.com', self.zkclient_mock,
                                    app_pattern='foo.kafka.*')
        self.assertEqual(len(brokers), 1)

    @mock.patch('treadmill.kafka.get_master_brokers',
                mock.Mock(return_value=[]))
    @mock.patch('treadmill.admin.Cell.get',
                mock.Mock(return_value={'masters': [{
                    'hostname': 'foo',
                    'kafka-client-port': 1111
                }]}))
    def test_get_brokers_from_cell(self):
        """Test getting the number of Kafka brokers from cell"""
        brokers = kafka.get_brokers('test', 'tm.xxx.com', self.zkclient_mock,
                                    app_pattern='foo.kafka.*')
        self.assertEqual(len(brokers), 1)

    @mock.patch('treadmill.admin.Cell.get',
                mock.Mock(return_value={'masters': [{
                    'hostname': 'foo'
                }]}))
    @mock.patch('treadmill.kafka._get_kafka_endpoint',
                mock.Mock(return_value=['foo.xx.com:12345']))
    @mock.patch('treadmill.admin.Application.list',
                mock.Mock(return_value=[{'_id': 'proid.app1'},
                                        {'_id': 'proid.app2'}]))
    def test_get_brokers_with_pattern(self):
        """Test getting the number of Kafka brokers with pattern & match"""
        brokers = kafka.get_brokers('test', 'tm.xxx.com', self.zkclient_mock,
                                    app_pattern='foo.kafka.*')
        self.assertEqual(len(brokers), 1)

    @mock.patch('treadmill.admin.Cell.get',
                mock.Mock(return_value={'masters': [{
                    'hostname': 'foo'
                }]}))
    @mock.patch('treadmill.kafka._get_kafka_endpoint',
                mock.Mock(return_value=[]))
    @mock.patch('treadmill.admin.Application.list',
                mock.Mock(return_value=[{'_id': 'proid.app1'}]))
    def test_get_brokers_no_match(self):
        """Test getting the number of Kafka brokers with pattern & no match"""
        brokers = kafka.get_brokers('test', 'tm.zzz.com', self.zkclient_mock,
                                    app_pattern='proid.kafka.*')
        self.assertEqual(len(brokers), 0)

    @mock.patch('treadmill.admin.Cell.get',
                mock.Mock(return_value={'masters': [{
                    'hostname': 'foo'
                }]}))
    @mock.patch('treadmill.kafka._get_kafka_endpoint',
                mock.Mock(return_value=['foo.xx.com:12345']))
    @mock.patch('treadmill.admin.Application.list',
                mock.Mock(return_value=[{'_id': 'proid.app1'},
                                        {'_id': 'proid.app2'}]))
    def test_get_brokers_no_pattern(self):
        """Test getting the number of Kafka brokers with no pattern & match"""
        # No pattern, use default pattern
        brokers = kafka.get_brokers('test', 'tm.xxx.com', self.zkclient_mock)
        self.assertEqual(len(brokers), 2)


if __name__ == '__main__':
    unittest.main()
