"""
Unit test for boto3 singleton connection
"""

import unittest
import mock

from treadmill.infra import connection


class ConnectionTest(unittest.TestCase):
    """Tests for boto3 connection singleton."""

    def setUp(self):
        connection.Connection._instances = {}

    def tearDown(self):
        connection.Connection._instances = {}

    @mock.patch('boto3.client', mock.Mock(return_value='foo'))
    def test_establish(self):
        conn = connection.Connection()
        connection.boto3.client.assert_called_with(
            'ec2', region_name=connection.Connection.context.region_name
        )
        self.assertEquals(conn, 'foo')

    @mock.patch('boto3.client', mock.Mock(return_value='foo'))
    def test_establish_with_region(self):
        connection.Connection.context.region_name = 'foobar'
        conn = connection.Connection()
        connection.boto3.client.assert_called_with('ec2', region_name='foobar')
        self.assertEquals(conn, 'foo')

    @mock.patch('boto3.client')
    def test_connection_singleton(self, client_mock):
        client_obj_mock = mock.Mock()
        client_obj_mock._service_model.service_name = 'EC2'
        client_mock.return_value = client_obj_mock
        conn1 = connection.Connection()
        conn2 = connection.Connection()
        connection.boto3.client.assert_called_once_with(
            'ec2', region_name=connection.Connection.context.region_name
        )
        self.assertEquals(conn1, conn2)


if __name__ == '__main__':
    unittest.main()
