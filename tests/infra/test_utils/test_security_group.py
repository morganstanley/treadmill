import unittest
import mock
from treadmill.infra.utils import security_group


class SecuirtyGroupTest(unittest.TestCase):
    @mock.patch('treadmill.infra.connection.Connection')
    def test_enable(self, connectionMock):
        conn = connectionMock()
        security_group.my_ip = '127.0.0.1'

        security_group.enable(group_id='sg-123', port='11')

        conn.authorize_security_group_ingress.assert_called_once_with(
            CidrIp='127.0.0.1',
            FromPort=11,
            ToPort=11,
            GroupId='sg-123',
            IpProtocol='tcp'
        )

    @mock.patch('treadmill.infra.connection.Connection')
    def test_disable(self, connectionMock):
        conn = connectionMock()
        security_group.my_ip = '127.0.0.1'

        security_group.disable(group_id='sg-123', port='33')

        conn.revoke_security_group_ingress.assert_called_once_with(
            CidrIp='127.0.0.1',
            FromPort=33,
            ToPort=33,
            GroupId='sg-123',
            IpProtocol='tcp'
        )
