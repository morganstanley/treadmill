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

import kazoo
import kazoo.client
import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import tickets
from treadmill.tickets import locker


class TicketLockerTest(unittest.TestCase):
    """Tests for treadmill.tickets.TicketLocker"""

    def setUp(self):
        self.tkt_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tkt_dir)

    @mock.patch('random.shuffle', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.gssapiprotocol.GSSAPILineClient')
    @mock.patch('treadmill.tickets.Ticket.copy', mock.Mock(spec_set=True))
    @mock.patch('treadmill.tickets.Ticket.write',
                mock.Mock(spec_set=True, side_effect=[False, True]))
    def test_request_tickets(self, client_cls):
        """Test parsing output of request_tickets."""
        treadmill.zkutils.connect.return_value = kazoo.client.KazooClient()
        kazoo.client.KazooClient.get_children.return_value = [
            'xxx.xx.com:1234', 'yyy.xx.com:1234', 'zzz.xx.com:1234'
        ]

        # base64.urlsafe_b64encode('abcd') : YWJjZA==
        lockers = {
            ('xxx.xx.com', 1234): [b'foo@bar:YWJjZA==', b''],
            ('yyy.xx.com', 1234): [b'foo@bar:YWJjZA==', b''],
            ('zzz.xx.com', 1234): [b'foo@bar:YWJjZA==', b''],
        }

        def create_mock_client(host, port):
            """Create mock client."""
            mock_client = mock.Mock()
            mock_client.read.side_effect = lambda: lockers[(host, port)].pop(0)
            return mock_client

        client_cls.side_effect = lambda host, port, _: create_mock_client(
            host, port
        )

        tickets.request_tickets(
            kazoo.client.KazooClient(),
            'myapp',
            self.tkt_dir,
            set(['foo@bar'])
        )

        tickets.Ticket.write.assert_called_with()
        self.assertEqual(tickets.Ticket.write.call_count, 2)

        tickets.Ticket.copy.assert_called_with(
            os.path.join(self.tkt_dir, 'foo@bar')
        )
        self.assertEqual(tickets.Ticket.copy.call_count, 1)

        # The first ticket was invalid (expired), had to try the second locker.
        self.assertEqual(len(lockers[('xxx.xx.com', 1234)]), 0)
        self.assertEqual(len(lockers[('yyy.xx.com', 1234)]), 0)
        self.assertEqual(len(lockers[('zzz.xx.com', 1234)]), 2)

    @mock.patch('kazoo.client.KazooClient.exists',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.zkutils.get', mock.Mock())
    def test_process_request(self):
        """Test processing ticket request."""
        treadmill.zkutils.get.return_value = {'tickets': ['tkt1']}
        tkt_locker = locker.TicketLocker(kazoo.client.KazooClient(),
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

    def test_process_trusted(self):
        """Test processing trusted app."""
        tkt_locker = locker.TicketLocker(
            kazoo.client.KazooClient(),
            self.tkt_dir,
            trusted={('aaa.xxx.com', 'master'): ['x@r1']}
        )
        with io.open(os.path.join(self.tkt_dir, 'x@r1'), 'w+') as f:
            f.write('x')

        # base64 encoded 'x'.
        self.assertEqual(
            {'x@r1': b'eA=='},
            tkt_locker.process_request('host/aaa.xxx.com@y.com', 'master')
        )

    @mock.patch('kazoo.client.KazooClient.exists',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.zkutils.get', mock.Mock())
    def test_process_request_noapp(self):
        """Test processing ticket request."""
        treadmill.zkutils.get.side_effect = kazoo.client.NoNodeError
        tkt_locker = locker.TicketLocker(kazoo.client.KazooClient(),
                                         '/var/spool/tickets')

        # With no node node error, result will be empty dict.
        self.assertEqual(
            {},
            tkt_locker.process_request('host/aaa.xxx.com@y.com', 'foo#1234'))

    @mock.patch('os.fchown', mock.Mock(spec_set=True))
    @mock.patch(
        'pwd.getpwnam',
        mock.Mock(
            spec_set=True,
            return_value=collections.namedtuple(
                'pwnam', ['pw_uid', 'pw_gid'])(3, 4)
        )
    )
    @mock.patch('treadmill.fs.rm_safe', mock.Mock(spec_set=True))
    @mock.patch('treadmill.tickets.krbcc_ok', mock.Mock(spec_set=True))
    def test_ticket_write_expired(self):
        """Tests expiration checking of ticket before writing to the file
        system.
        """
        tkt = tickets.Ticket('uid@realm', b'content')
        tkt_path = os.path.join(self.tkt_dir, 'x')
        tickets.krbcc_ok.return_value = False
        res = tkt.write(tkt_path)

        self.assertFalse(res)
        self.assertFalse(os.path.exists(tkt_path))
        treadmill.fs.rm_safe.assert_called_with(mock.ANY)

    @mock.patch('os.fchown', mock.Mock(spec_set=True))
    @mock.patch(
        'pwd.getpwnam',
        mock.Mock(
            spec_set=True,
            return_value=collections.namedtuple(
                'pwnam', ['pw_uid', 'pw_gid'])(3, 4)
        )
    )
    @mock.patch('treadmill.fs.rm_safe', mock.Mock(spec_set=True))
    @mock.patch('treadmill.tickets.krbcc_ok',
                mock.Mock(spec_set=True, return_value=True))
    def test_ticket_write(self):
        """Tests writing ticket to the file system.
        """
        tkt = tickets.Ticket('uid@realm', b'content')
        test_tkt_path = '/tmp/krb5cc_%d' % 3

        self.assertEqual(tkt.tkt_path, test_tkt_path)
        res = tkt.write()

        self.assertTrue(res)
        self.assertTrue(os.path.exists(test_tkt_path))
        treadmill.fs.rm_safe.assert_called_with(mock.ANY)

    @mock.patch('os.fchown', mock.Mock(spec_set=True))
    @mock.patch(
        'pwd.getpwnam',
        mock.Mock(
            spec_set=True,
            return_value=collections.namedtuple(
                'pwnam', ['pw_uid', 'pw_gid'])(3, 4)
        )
    )
    @mock.patch('treadmill.fs.rm_safe', mock.Mock(spec_set=True))
    def test_ticket_copy(self):
        """Test copying tickets.
        """
        tkt = tickets.Ticket('uid@realm', b'content')
        test_tkt_path = os.path.join(self.tkt_dir, 'foo')
        # touch a ticket
        with io.open(tkt.tkt_path, 'wb'):
            pass

        tkt.copy(dst=test_tkt_path)

        self.assertTrue(os.path.exists(test_tkt_path))
        os.fchown.assert_called_with(mock.ANY, 3, -1)
        treadmill.fs.rm_safe.assert_called_with(mock.ANY)

    @mock.patch('treadmill.fs.symlink_safe', mock.Mock())
    @mock.patch('treadmill.tickets.Ticket.copy', mock.Mock(spec_set=True))
    @mock.patch('treadmill.tickets.Ticket.write',
                mock.Mock(spec_set=True, return_value=True))
    def test_store_ticket(self):
        """Test storing tickets.
        """
        tkt = tickets.Ticket('uid@realm', b'content')

        res = tickets.store_ticket(tkt, '/var/spool/tickets')

        self.assertTrue(res)
        treadmill.fs.symlink_safe.assert_called_with(
            '/var/spool/tickets/uid', 'uid@realm'
        )

    @mock.patch('treadmill.fs.symlink_safe', mock.Mock())
    @mock.patch('treadmill.tickets.Ticket.copy', mock.Mock(spec_set=True))
    @mock.patch('treadmill.tickets.Ticket.write',
                mock.Mock(spec_set=True, return_value=False))
    def test_store_ticket_expired(self):
        """Test storing invalid (expired) tickets.
        """
        tkt = tickets.Ticket('uid@realm', b'content')

        res = tickets.store_ticket(tkt, '/var/spool/tickets')

        self.assertFalse(res)
        treadmill.fs.symlink_safe.assert_not_called()


if __name__ == '__main__':
    unittest.main()
