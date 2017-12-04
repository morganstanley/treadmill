"""Tests for treadmill.tickets module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import collections
import os
import unittest
import tempfile
import shutil

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import kazoo
import kazoo.client
import mock

import treadmill
from treadmill import tickets
from treadmill import zkutils


class TicketLockerTest(unittest.TestCase):
    """Tests for treadmill.tickets.TicketLocker"""

    def setUp(self):
        self.tkt_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tkt_dir)

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

        self.assertEqual([tickets.Ticket('foo@bar', b'abcd')], reply)

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

    @mock.patch('kazoo.client.KazooClient.get_children',
                mock.Mock(return_value=[]))
    @mock.patch('treadmill.subproc.check_output',
                mock.Mock(return_value='klist-output'))
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_exists', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname', mock.Mock(return_value='h'))
    def test_publish(self):
        """Test tickets publishing."""
        tkt_locker = tickets.TicketLocker(kazoo.client.KazooClient(),
                                          self.tkt_dir)
        io.open(os.path.join(self.tkt_dir, 'x@r1'), 'w+').close()
        io.open(os.path.join(self.tkt_dir, 'x@r2'), 'w+').close()
        io.open(os.path.join(self.tkt_dir, 'x@r3'), 'w+').close()

        tkt_locker.publish_tickets(['@r1', '@r2'], once=True)
        treadmill.zkutils.put.assert_has_calls([
            mock.call(mock.ANY, '/tickets/x@r1/h', 'klist-output',
                      ephemeral=True),
            mock.call(mock.ANY, '/tickets/x@r2/h', 'klist-output',
                      ephemeral=True),
        ], any_order=True)

    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children',
                mock.Mock(return_value=['x@r1']))
    @mock.patch('treadmill.tickets.krbcc_ok', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname', mock.Mock(return_value='h'))
    def test_prune(self):
        """Test pruning published tickets."""
        tkt_locker = tickets.TicketLocker(kazoo.client.KazooClient(),
                                          self.tkt_dir)
        tickets.krbcc_ok.return_value = True
        tkt_locker.prune_tickets()

        tickets.krbcc_ok.assert_called_with(
            os.path.join(self.tkt_dir, 'x@r1'))
        self.assertFalse(zkutils.ensure_deleted.called)

        tickets.krbcc_ok.reset_mock()
        tickets.krbcc_ok.return_value = False
        tkt_locker.prune_tickets()

        tickets.krbcc_ok.assert_called_with(
            os.path.join(self.tkt_dir, 'x@r1'))
        zkutils.ensure_deleted.assert_called_with(mock.ANY, '/tickets/x@r1/h')

    @mock.patch('os.chown', mock.Mock())
    @mock.patch('treadmill.tickets.krbcc_ok', mock.Mock())
    def test_ticket_write(self):
        """Tests writing ticket to the file system."""
        tkt = tickets.Ticket('uid@realm', b'content')
        tkt_path = os.path.join(self.tkt_dir, 'x')
        tickets.krbcc_ok.return_value = False
        tkt.write(tkt_path)
        self.assertFalse(os.path.exists(tkt_path))

        tickets.krbcc_ok.return_value = True
        tkt.write(tkt_path)
        self.assertTrue(os.path.exists(tkt_path))


if __name__ == '__main__':
    unittest.main()
