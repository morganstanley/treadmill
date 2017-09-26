"""Tests for treadmill.tickets module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import unittest

import kazoo
import kazoo.client
import mock

import treadmill
from treadmill import tickets


class TicketLockerTest(unittest.TestCase):
    """Tests for treadmill.tickets.TicketLocker"""

    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.gssapiprotocol.GSSAPILineClient.connect',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.gssapiprotocol.GSSAPILineClient.disconnect',
                mock.Mock())
    @mock.patch('treadmill.gssapiprotocol.GSSAPILineClient.write', mock.Mock())
    @mock.patch('treadmill.gssapiprotocol.GSSAPILineClient.read', mock.Mock())
    @mock.patch('pwd.getpwnam', mock.Mock(
        return_value=collections.namedtuple('pwnam', ['pw_uid'])(3)))
    def test_request_tickets(self):
        """Test parsing output of request_tickets."""
        treadmill.zkutils.connect.return_value = kazoo.client.KazooClient()
        kazoo.client.KazooClient.get_children.return_value = [
            'xxx.xx.com:1234', 'yyy.xx.com:1234'
        ]
        # base64.urlsafe_b64encode('abcd') : YWJjZA==
        lines = [b'foo@bar:YWJjZA==', b'']
        treadmill.gssapiprotocol.GSSAPILineClient.read.side_effect = (
            lambda: lines.pop(0))

        reply = tickets.request_tickets(kazoo.client.KazooClient(), 'myapp')

        self.assertEqual([tickets.Ticket('foo@bar', 'abcd')], reply)

    @mock.patch('kazoo.client.KazooClient.exists',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.zkutils.get', mock.Mock())
    def test_process_request(self):
        """Test processing ticket request."""
        treadmill.zkutils.get.return_value = {'tickets': ['tkt1']}
        tkt_locker = tickets.TicketLocker(kazoo.client.KazooClient(),
                                          '/var/spool/tickets')

        # With no ticket in /var/spool/tickets, result will be empty dict
        self.assertEqual(
            {},
            tkt_locker.process_request('host/aaa.xxx.com@y.com', 'foo#1234'))

        kazoo.client.KazooClient.exists.assert_called_with(
            '/placement/aaa.xxx.com/foo#1234')

        # Invalid (non host) principal
        self.assertEqual(
            None,
            tkt_locker.process_request('aaa.xxx.com@y.com', 'foo#1234'))

    @mock.patch('kazoo.client.KazooClient.exists',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.zkutils.get', mock.Mock())
    def test_process_request_noapp(self):
        """Test processing ticket request."""
        treadmill.zkutils.get.side_effect = kazoo.client.NoNodeError
        tkt_locker = tickets.TicketLocker(kazoo.client.KazooClient(),
                                          '/var/spool/tickets')

        # With no node node error, result will be empty dict.
        self.assertEqual(
            {},
            tkt_locker.process_request('host/aaa.xxx.com@y.com', 'foo#1234'))


if __name__ == '__main__':
    unittest.main()
