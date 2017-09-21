import unittest
import mock
from treadmill.infra.utils import security_group


class SecuirtyGroupTest(unittest.TestCase):
    @mock.patch('urllib.request.urlopen')
    @mock.patch('treadmill.infra.connection.Connection')
    def test_enable_for_my_ip(self, connectionMock, requestMock):
        http_response_mock = mock.Mock()
        http_response_mock.read.side_effect = [b'so.me.i.p']
        requestMock.return_value = http_response_mock
        conn = connectionMock()

        security_group.enable(group_id='sg-123', port='11', anywhere=False)

        conn.authorize_security_group_ingress.assert_called_once_with(
            CidrIp='so.me.i.p/32',
            FromPort=11,
            ToPort=11,
            GroupId='sg-123',
            IpProtocol='tcp'
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_enable_for_anywhere(self, connectionMock):
        conn = connectionMock()

        security_group.enable(group_id='sg-123', port='11')

        conn.authorize_security_group_ingress.assert_called_once_with(
            CidrIp='0.0.0.0/0',
            FromPort=11,
            ToPort=11,
            GroupId='sg-123',
            IpProtocol='tcp'
        )

    @mock.patch('urllib.request.urlopen')
    @mock.patch('treadmill.infra.connection.Connection')
    def test_disable_for_my_ip(self, connectionMock, requestMock):
        http_response_mock = mock.Mock()
        http_response_mock.read.side_effect = [b'so.me.i.p']
        requestMock.return_value = http_response_mock
        conn = connectionMock()

        security_group.disable(group_id='sg-123', port='33', anywhere=False)

        conn.revoke_security_group_ingress.assert_called_once_with(
            CidrIp='so.me.i.p/32',
            FromPort=33,
            ToPort=33,
            GroupId='sg-123',
            IpProtocol='tcp'
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_disable_for_anywhere(self, connectionMock):
        conn = connectionMock()

        security_group.disable(group_id='sg-123', port='33')

        conn.revoke_security_group_ingress.assert_called_once_with(
            CidrIp='0.0.0.0/0',
            FromPort=33,
            ToPort=33,
            GroupId='sg-123',
            IpProtocol='tcp'
        )
