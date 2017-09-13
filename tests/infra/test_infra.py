"""
Unit test for treadmill infra.
"""

import unittest
import mock

from treadmill import infra


class InfraTest(unittest.TestCase):
    """Tests treadmill infra"""

    @mock.patch('treadmill.infra.connection.Connection')
    def test_create_iam_role(self, ConnectionMock):
        "Test create IAM role"
        iam_conn_mock = ConnectionMock()
        iam_conn_mock.create_role = mock.Mock(return_value='custom_role')
        role = infra.create_iam_role(name='foo')
        self.assertEquals(role, 'custom_role')
        iam_conn_mock.create_role.assert_called_once()
        iam_conn_mock.create_instance_profile.assert_called_once_with(
            InstanceProfileName='foo'
        )
        iam_conn_mock.add_role_to_instance_profile.assert_called_once_with(
            RoleName='foo',
            InstanceProfileName='foo'
        )

    @mock.patch('treadmill.infra.connection.Connection')
    @mock.patch('treadmill.infra.create_iam_role')
    def test_get_iam_role(self, create_iam_role_mock, ConnectionMock):
        "Test get IAM role"
        iam_conn_mock = ConnectionMock()
        iam_conn_mock.get_role = mock.Mock(return_value='custom_role')
        role = infra.get_iam_role(
            name='Test_Role', create=False
        )
        self.assertEquals(role, 'custom_role')
        iam_conn_mock.get_role.assert_called_once_with(
            RoleName='Test_Role'
        )
        create_iam_role_mock.assert_not_called()
