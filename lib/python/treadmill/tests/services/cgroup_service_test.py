"""Unit test for cgroup_service - Treadmill cgroup service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import tempfile
import unittest
import select
import shutil

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import services
from treadmill.services import cgroup_service


class CGroupServiceTest(unittest.TestCase):
    """Unit tests for the cgroup service implementation.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.cgroup_svc = os.path.join(self.root, 'cgroup_svc')
        self.running = os.path.join(self.root, 'running')

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_initialize(self):
        """Test service initialization.
        """
        svc = cgroup_service.CgroupResourceService(self.running, 'treadmill')
        svc.initialize(self.cgroup_svc)

    def test_report_status(self):
        """Test processing of status request.
        """
        svc = cgroup_service.CgroupResourceService(self.running, 'treadmill')
        status = svc.report_status()

        self.assertEqual(
            status,
            {'ready': True}
        )

    def test_event_handlers(self):
        """Test event_handlers request.
        """
        svc = cgroup_service.CgroupResourceService(self.running, 'treadmill')
        handlers = svc.event_handlers()

        self.assertEqual(
            handlers,
            []
        )

    @mock.patch('treadmill.cgroups.create', mock.Mock())
    @mock.patch('treadmill.cgroups.get_value', mock.Mock(return_value=10000))
    @mock.patch('treadmill.cgroups.inherit_value', mock.Mock())
    @mock.patch('treadmill.cgroups.join', mock.Mock())
    @mock.patch('treadmill.cgroups.set_value', mock.Mock())
    @mock.patch('treadmill.services.cgroup_service.CgroupResourceService.'
                '_register_oom_handler', mock.Mock())
    def test_on_create_request(self):
        """Test processing of a cgroups create request.
        """
        # Access to a protected member _register_oom_handler of a client class
        # pylint: disable=W0212
        svc = cgroup_service.CgroupResourceService(self.running,
                                                   'treadmill.slice')

        request = {
            'memory': '100M',
            'cpu': '100%',
        }
        request_id = 'myproid.test-0-ID1234'

        svc.on_create_request(request_id, request)

        cgrp = os.path.join('treadmill.slice/apps', request_id)
        svc._register_oom_handler.assert_called_with(cgrp, request_id)
        treadmill.cgroups.create.assert_has_calls(
            [
                mock.call(ss, cgrp)
                for ss in ['cpu', 'cpuacct', 'cpuset', 'memory', 'blkio']
            ] + [
                mock.call(ss, os.path.join(cgrp, 'services'))
                for ss in ['cpu', 'cpuacct', 'cpuset', 'memory', 'blkio']
            ],
            any_order=True
        )

        # Memory calculation:
        #
        # (demand  * virtual cpu bmips / total bmips) * treadmill.cpu.shares
        # (100%    * 5000              / (24000 * 0.9 ) * 10000) = 2314
        treadmill.cgroups.set_value.assert_has_calls([
            mock.call('blkio', cgrp, 'blkio.weight', 100),
            mock.call('memory', cgrp, 'memory.soft_limit_in_bytes', '100M'),
            mock.call('memory', cgrp, 'memory.limit_in_bytes', '100M'),
            mock.call('memory', cgrp, 'memory.memsw.limit_in_bytes', '100M'),
            mock.call('cpu', cgrp, 'cpu.shares',
                      treadmill.sysinfo.BMIPS_PER_CPU)
        ])

        treadmill.cgroups.inherit_value.assert_has_calls([
            mock.call('cpuset', cgrp, 'cpuset.cpus'),
            mock.call('cpuset', cgrp, 'cpuset.mems')
        ])

    @mock.patch('treadmill.cgutils.delete', mock.Mock())
    @mock.patch('treadmill.services.cgroup_service.CgroupResourceService.'
                '_unregister_oom_handler', mock.Mock())
    def test_on_delete_request(self):
        """Test processing of a cgroups delete request.
        """
        # Access to a protected member _unregister_oom_handler of a client
        # class
        # pylint: disable=W0212
        svc = cgroup_service.CgroupResourceService(self.running,
                                                   'treadmill.slice')

        request_id = 'myproid.test-0-ID1234'

        svc.on_delete_request(request_id)

        cgrp = os.path.join('treadmill.slice/apps', request_id)
        treadmill.cgutils.delete.assert_has_calls(
            [
                mock.call(ss, cgrp)
                for ss in ['cpu', 'cpuacct', 'cpuset', 'memory', 'blkio']
            ]
        )
        svc._unregister_oom_handler.assert_called_with(cgrp)

    @mock.patch('treadmill.cgutils.get_memory_oom_eventfd',
                mock.Mock(return_value='fake_efd'))
    def test__register_oom_handler(self):
        """Test registration of OOM handler.
        """
        # Access to a protected member _register_oom_handler of a client class
        # pylint: disable=W0212
        svc = cgroup_service.CgroupResourceService(self.running,
                                                   'treadmill.slice')
        registered_handlers = svc.event_handlers()
        self.assertNotIn(
            ('fake_efd', select.POLLIN, mock.ANY),
            registered_handlers
        )
        cgrp = 'treadmill.slice/apps/myproid.test-42-ID1234'

        svc._register_oom_handler(cgrp, 'myproid.test-42-ID1234')

        treadmill.cgutils.get_memory_oom_eventfd.assert_called_with(cgrp)
        registered_handlers = svc.event_handlers()
        self.assertIn(
            ('fake_efd', select.POLLIN, mock.ANY),
            registered_handlers
        )

    @mock.patch('os.close', mock.Mock())
    @mock.patch('treadmill.cgutils.get_memory_oom_eventfd',
                mock.Mock(return_value='fake_efd'))
    def test__unregister_oom_handler(self):
        """Test unregistration of OOM handler.
        """
        # Access to a protected member _unregister_oom_handler of a client
        # class
        # pylint: disable=W0212
        svc = cgroup_service.CgroupResourceService(self.running,
                                                   'treadmill.slice')
        cgrp = 'treadmill.slice/apps/myproid.test-42-ID1234'
        svc._register_oom_handler(cgrp, 'myproid.test-42-ID1234')
        registered_handlers = svc.event_handlers()
        self.assertIn(
            ('fake_efd', select.POLLIN, mock.ANY),
            registered_handlers
        )

        svc._unregister_oom_handler(cgrp)

        registered_handlers = svc.event_handlers()
        self.assertNotIn(
            ('fake_efd', select.POLLIN, mock.ANY),
            registered_handlers
        )
        os.close.assert_called_with('fake_efd')

    def test_load(self):
        """Test loading service using alias."""
        # pylint: disable=W0212
        self.assertEqual(
            cgroup_service.CgroupResourceService,
            services.ResourceService(self.root, 'cgroup')._load_impl()
        )


if __name__ == '__main__':
    unittest.main()
