"""Unit test for base_service - Basic Treadmill service capabilities.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import tempfile
import unittest
import select
import socket
import sys

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import services


class MyTestService(services.BaseResourceServiceImpl):
    """Test Service implementation.
    """
    def __init__(self, *_args, **_kw_args):
        super(MyTestService, self).__init__()

    def initialize(self, service_dir):
        pass

    def on_create_request(self, _rsrc_id, _rsrc_data):
        pass

    def on_delete_request(self, _rsrc_id):
        pass

    def report_status(self):
        pass

    def synchronize(self):
        pass


class BaseServiceTest(unittest.TestCase):
    """Unit tests for the base service class.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_init(self):
        """Validate simple instanciation.
        """
        instance = services.ResourceService(
            service_dir=self.root,
            impl='a.sample.module',
        )

        self.assertEqual(
            instance.name,
            'module'
        )

    def test_load(self):
        """Verifies that only valid classes are accepted as implementation.
        """
        # Access to a protected member _load_impl of a client class
        # pylint: disable=W0212

        self.assertRaises(
            AssertionError,
            services.ResourceService(
                service_dir=self.root,
                impl=object,
            )._load_impl
        )
        self.assertRaises(
            KeyError,
            services.ResourceService(
                service_dir=self.root,
                impl='socket:socket',
            )._load_impl
        )

        self.assertTrue(
            services.ResourceService(
                service_dir=self.root,
                impl=MyTestService,
            )._load_impl()
        )

    def test_name(self):
        """Check how the name is derived from the class name.
        """
        self.assertEqual(
            services.ResourceService(
                service_dir=self.root,
                impl='treadmill.services.MyClass',
            ).name,
            'MyClass',
        )
        self.assertEqual(
            services.ResourceService(
                service_dir=self.root,
                impl='treadmill.services.MyClass',
            ).name,
            'MyClass',
        )
        self.assertEqual(
            services.ResourceService(
                service_dir=self.root,
                impl=MyTestService,
            ).name,
            'MyTestService',
        )

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('select.poll', autospec=True)
    @mock.patch('treadmill.dirwatch.DirWatcher', autospec=True)
    @mock.patch('treadmill.services._linux_base_service.LinuxResourceService'
                '._create_status_socket',
                mock.Mock(return_value='status_socket'))
    @mock.patch('treadmill.services._linux_base_service.LinuxResourceService'
                '._check_requests',
                mock.Mock(return_value=['foo-1', 'foo-2']))
    @mock.patch('treadmill.services._linux_base_service.LinuxResourceService'
                '._load_impl',
                return_value=mock.create_autospec(MyTestService))
    @mock.patch('treadmill.services._linux_base_service.LinuxResourceService'
                '._on_created',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.services._linux_base_service.LinuxResourceService'
                '._update_poll_registration',
                mock.Mock())
    @mock.patch('treadmill.watchdog.Watchdog', autospec=True)
    @mock.patch('treadmill.syscall.eventfd.eventfd',
                mock.Mock(return_value='eventfd'))
    def test_linux_run(self, mock_watchdog, mock_load_impl, mock_dirwatcher,
                       mock_poll):
        """Test the run method setup before the main loop.
        """
        # Access to a protected member _is_dead of a client class
        # pylint: disable=W0212

        mock_impl_instance = mock_load_impl.return_value.return_value
        mock_impl_instance.configure_mock(
            WATCHDOG_HEARTBEAT_SEC=60
        )
        mock_impl_instance.report_status.return_value = {
            'hello': 'world'
        }
        mock_impl_instance.event_handlers.return_value = [
            ('filenoA', 'eventsA', 'callbackA'),
            ('filenoB', 'eventsB', 'callbackB'),
        ]
        mock_dirwatcher.return_value.configure_mock(
            inotify='mock_inotiy',
        )
        instance = services.ResourceService(
            service_dir=self.root,
            impl='MyTestService',
        )

        instance._is_dead = True
        instance.run(
            os.path.join(self.root, 'watchdogs'),
            'foo',
            bar='baz',
        )

        mock_load_impl.assert_called_with()
        # Make sure the implementation was passed the correct parameters.
        mock_load_impl.return_value.assert_called_with(
            'foo',
            bar='baz',
        )

        # Watchdog should be set
        mock_watchdog.assert_called_with(
            os.path.join(self.root, 'watchdogs'),
        )
        mock_watchdog.return_value.create.assert_called_with(
            content=mock.ANY,
            name='svc-MyTestService',
            timeout='60s'
        )
        mock_watchdog_lease = mock_watchdog.return_value.create.return_value

        # Implementation should be given the root as argument to `initialize`
        mock_impl_instance.initialize.assert_called_with(
            self.root
        )
        # First watcher should be setup
        mock_dirwatcher.assert_called_with(
            os.path.join(self.root, 'resources')
        )
        # Then we check/cleanup pre-existing requests
        services.ResourceService._check_requests.assert_called_with()
        services.ResourceService._on_created.assert_has_calls([
            mock.call(mock_impl_instance, 'foo-1'),
            mock.call(mock_impl_instance, 'foo-2'),
        ])
        # Status should be queried first
        mock_impl_instance.report_status.assert_called_with()

        # The poll registration should be properly initialized
        mock_impl_instance.event_handlers.assert_called_with()
        instance._update_poll_registration.assert_called_with(
            mock_poll.return_value,
            {},
            [
                ('eventfd', mock.ANY, mock.ANY),
                ('mock_inotiy', mock.ANY, mock.ANY),
                ('status_socket', mock.ANY, mock.ANY),
                ('filenoA', mock.ANY, mock.ANY),
                ('filenoB', mock.ANY, mock.ANY),
            ],
        )

        # Loop exits immediately

        # Watchdog lease should be cleared
        mock_watchdog_lease.remove.assert_called_with()

    # Disable C0103(invalid-name) as the name is too long
    # pylint: disable=C0103
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('os.chmod', mock.Mock())
    @mock.patch('os.unlink', mock.Mock())
    @mock.patch('socket.socket', auto_spec=True)
    def test_linux__create_status_socket(self, mock_sock):
        """Test status socket creation.
        """
        # Access to a protected member _create_status_socket of a client class
        # pylint: disable=W0212

        mock_self = mock.Mock(
            spec_set=services.ResourceService,
            status_sock='/tmp/foo',
        )

        treadmill.services._linux_base_service.LinuxResourceService\
            ._create_status_socket(mock_self,)

        os.unlink.assert_called_with(
            '/tmp/foo'
        )
        mock_sock.assert_called_with(
            family=socket.AF_UNIX,
            type=socket.SOCK_STREAM,
            proto=0
        )
        mock_socket = mock_sock.return_value
        mock_socket.bind.assert_called_with(
            '/tmp/foo'
        )
        mock_socket.listen.assert_called_with(mock.ANY)
        os.chmod.assert_called_with(
            '/tmp/foo', 0o666
        )

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('select.poll', autospec=True)
    def test_linux__run_events(self, mock_poll):
        """Test event dispatcher.
        """
        # Access to a protected member _run_events of a client class
        # pylint: disable=W0212

        instance = services.ResourceService(
            service_dir=self.root,
            impl='a.sample.module',
        )
        mock_callbacks = {
            i: {'callback': mock.Mock(return_value=i)}
            for i in range(3)
        }
        loop_poll = mock_poll.return_value
        loop_poll.poll.return_value = ((i, select.POLLIN) for i in range(2))

        res = instance._run_events(loop_poll, 42, mock_callbacks)

        loop_poll.poll.assert_called_with(42 * 1000)
        self.assertTrue(mock_callbacks[0]['callback'].called)
        self.assertTrue(mock_callbacks[1]['callback'].called)
        self.assertFalse(mock_callbacks[2]['callback'].called)

        self.assertTrue(res)


if __name__ == '__main__':
    unittest.main()
