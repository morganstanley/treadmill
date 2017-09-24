"""Unit test for treadmill.runtime.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import socket
import unittest

import mock

import treadmill
import treadmill.rulefile
import treadmill.runtime

from treadmill import exc


class RuntimeTest(unittest.TestCase):
    """Tests for treadmill.runtime."""

    @mock.patch('socket.socket.bind', mock.Mock())
    def test__allocate_sockets(self):
        """Test allocating sockets.
        """
        # access protected module _allocate_sockets
        # pylint: disable=w0212

        socket.socket.bind.side_effect = [
            socket.error(errno.EADDRINUSE, 'In use'),
            mock.DEFAULT,
            mock.DEFAULT,
            mock.DEFAULT
        ]

        sockets = treadmill.runtime._allocate_sockets(
            'prod', '0.0.0.0', socket.SOCK_STREAM, 3
        )

        self.assertEqual(3, len(sockets))

    @mock.patch('socket.socket.bind', mock.Mock())
    def test__allocate_sockets_fail(self):
        """Test allocating sockets when all are taken.
        """
        # access protected module _allocate_sockets
        # pylint: disable=w0212

        socket.socket.bind.side_effect = socket.error(errno.EADDRINUSE,
                                                      'In use')

        with self.assertRaises(exc.ContainerSetupError):
            treadmill.runtime._allocate_sockets(
                'prod', '0.0.0.0', socket.SOCK_STREAM, 3
            )

    @mock.patch('socket.socket', mock.Mock(autospec=True))
    @mock.patch('treadmill.runtime._allocate_sockets', mock.Mock())
    def test_allocate_network_ports(self):
        """Test network port allocation.
        """
        # access protected module _allocate_network_ports
        # pylint: disable=w0212
        treadmill.runtime._allocate_sockets.side_effect = \
            lambda _x, _y, _z, count: [socket.socket()] * count
        mock_socket = socket.socket.return_value
        mock_socket.getsockname.side_effect = [
            ('unused', 50001),
            ('unused', 60001),
            ('unused', 10000),
            ('unused', 10001),
            ('unused', 10002),
            ('unused', 12345),
            ('unused', 54321),
        ]
        manifest = {
            'type': 'native',
            'environment': 'dev',
            'endpoints': [
                {
                    'name': 'http',
                    'port': 8000,
                    'proto': 'tcp',
                }, {
                    'name': 'ssh',
                    'port': 0,
                    'proto': 'tcp',
                }, {
                    'name': 'dns',
                    'port': 5353,
                    'proto': 'udp',
                }, {
                    'name': 'port0',
                    'port': 0,
                    'proto': 'udp',
                }
            ],
            'ephemeral_ports': {'tcp': 3, 'udp': 0},
        }

        treadmill.runtime.allocate_network_ports(
            '1.2.3.4',
            manifest
        )

        # in the updated manifest, make sure that real_port is specificed from
        # the ephemeral range as returnd by getsockname.
        self.assertEqual(
            8000,
            manifest['endpoints'][0]['port']
        )
        self.assertEqual(
            50001,
            manifest['endpoints'][0]['real_port']
        )
        self.assertEqual(
            60001,
            manifest['endpoints'][1]['port']
        )
        self.assertEqual(
            60001,
            manifest['endpoints'][1]['real_port']
        )
        self.assertEqual(
            5353,
            manifest['endpoints'][2]['port']
        )
        self.assertEqual(
            12345,
            manifest['endpoints'][2]['real_port']
        )
        self.assertEqual(
            54321,
            manifest['endpoints'][3]['port']
        )
        self.assertEqual(
            54321,
            manifest['endpoints'][3]['real_port']
        )
        self.assertEqual(
            [10000, 10001, 10002],
            manifest['ephemeral_ports']['tcp']
        )


if __name__ == '__main__':
    unittest.main()
