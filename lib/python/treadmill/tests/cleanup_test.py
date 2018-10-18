"""Unit test for cleanup - cleanup node apps
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import os
import shutil
import tempfile
import unittest

import mock

import treadmill
import treadmill.runtime.runtime_base
from treadmill import cleanup
from treadmill import supervisor


class CleanupTest(unittest.TestCase):
    """Mock test for treadmill.cleanup.Cleanup.
    """
    @mock.patch('treadmill.appenv.AppEnvironment', mock.Mock(autospec=True))
    @mock.patch('treadmill.watchdog.Watchdog', mock.Mock(autospec=True))
    def setUp(self):
        self.root = tempfile.mkdtemp()

        self.cleanup_dir = os.path.join(self.root, 'cleanup')
        self.cleaning_dir = os.path.join(self.root, 'cleaning')
        self.cleanup_apps_dir = os.path.join(self.root, 'cleanup_apps')
        self.cleanup_tombstone_dir = os.path.join(
            self.root, 'tombstones', 'cleanup'
        )

        for tmp_dir in [self.cleanup_dir, self.cleaning_dir,
                        self.cleanup_apps_dir]:
            os.mkdir(tmp_dir)

        self.tm_env = mock.Mock(
            root=self.root,
            cleanup_dir=self.cleanup_dir,
            cleaning_dir=self.cleaning_dir,
            cleanup_apps_dir=self.cleanup_apps_dir,
            cleanup_tombstone_dir=self.cleanup_tombstone_dir
        )

        self.cleanup = cleanup.Cleanup(self.tm_env)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.supervisor.control_svscan', mock.Mock())
    def test__refresh_supervisor(self):
        """Check how the supervisor is being refreshed.
        """
        # Access to a protected member _refresh_supervisor of a client class
        # pylint: disable=W0212
        self.cleanup._refresh_supervisor()

        treadmill.supervisor.control_svscan.assert_called_with(
            self.cleaning_dir, (
                treadmill.supervisor.SvscanControlAction.alarm,
                treadmill.supervisor.SvscanControlAction.nuke
            )
        )

    @mock.patch('os.path.islink', mock.Mock())
    @mock.patch('treadmill.supervisor.create_service', mock.Mock())
    @mock.patch('treadmill.fs.symlink_safe', mock.Mock())
    @mock.patch('treadmill.cleanup.Cleanup._refresh_supervisor', mock.Mock())
    @mock.patch('treadmill.subproc.resolve',
                mock.Mock(return_value='/x/y/bin/treadmill'))
    def test__add_cleanup_app(self):
        """Tests that a new cleanup app is correctly configured.
        """
        # Access to a protected member _add_cleanup_app of a client class
        # pylint: disable=W0212
        os.path.islink.side_effect = [False, True]

        self.cleanup._add_cleanup_app(
            os.path.join(self.cleanup_dir, 'proid.app#0000000000001'))

        treadmill.supervisor.create_service.assert_called_with(
            self.cleanup_apps_dir,
            name='proid.app#0000000000001',
            app_run_script=mock.ANY,
            userid='root',
            monitor_policy={
                'limit': 5,
                'interval': 60,
                'tombstone': {
                    'path': self.cleanup_tombstone_dir,
                    'id': 'proid.app#0000000000001',
                },
                'skip_path': os.path.join(self.cleanup_dir,
                                          'proid.app#0000000000001')
            },
            log_run_script=None,
        )

        treadmill.fs.symlink_safe.assert_called_with(
            os.path.join(self.cleaning_dir, 'proid.app#0000000000001'),
            os.path.join(self.cleanup_apps_dir, 'proid.app#0000000000001')
        )

        treadmill.cleanup.Cleanup._refresh_supervisor.assert_called()

    @mock.patch('os.path.islink', mock.Mock())
    @mock.patch('treadmill.supervisor.create_service', mock.Mock())
    def test__add_cleanup_app_exists(self):
        """Tests add app when already exists.
        """
        # Access to a protected member _add_cleanup_app of a client class
        # pylint: disable=W0212
        os.path.islink.side_effect = [True]

        self.cleanup._add_cleanup_app(
            os.path.join(self.cleanup_dir, 'proid.app#0000000000001'))

        treadmill.supervisor.create_service.assert_not_called()

    # Disable C0103(Invalid method name)
    # pylint: disable=C0103
    @mock.patch('os.path.islink', mock.Mock())
    @mock.patch('treadmill.supervisor.create_service', mock.Mock())
    def test__add_cleanup_app_not_exists(self):
        """Tests add app when cleanup link does not exist.
        """
        # Access to a protected member _add_cleanup_app of a client class
        # pylint: disable=W0212
        os.path.islink.side_effect = [False, False]

        self.cleanup._add_cleanup_app(
            os.path.join(self.cleanup_dir, 'proid.app#0000000000001'))

        treadmill.supervisor.create_service.assert_not_called()

    @mock.patch('treadmill.supervisor.create_service', mock.Mock())
    def test__add_cleanup_app_temp(self):
        """Tests add app when cleanup link is a temp file
        """
        # Access to a protected member _add_cleanup_app of a client class
        # pylint: disable=W0212
        self.cleanup._add_cleanup_app(
            os.path.join(self.cleanup_dir, '.sdfasdfds'))

        treadmill.supervisor.create_service.assert_not_called()

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('treadmill.supervisor.ensure_not_supervised', mock.Mock())
    @mock.patch('treadmill.fs.rm_safe', mock.Mock())
    @mock.patch('treadmill.fs.rmtree_safe', mock.Mock())
    @mock.patch('treadmill.cleanup.Cleanup._refresh_supervisor', mock.Mock())
    def test__remove_cleanup_app(self):
        """Tests that a cleanup app is properly removed.
        """
        # Access to a protected member _remove_cleanup_app of a client class
        # pylint: disable=W0212
        os.path.exists.side_effect = [True]

        self.cleanup._remove_cleanup_app(
            os.path.join(self.cleanup_dir, 'proid.app#0000000000001'))

        treadmill.fs.rm_safe.assert_called_with(
            os.path.join(self.cleaning_dir, 'proid.app#0000000000001')
        )

        treadmill.cleanup.Cleanup._refresh_supervisor.assert_called()
        treadmill.supervisor.ensure_not_supervised.assert_called()

        treadmill.fs.rmtree_safe.assert_called_with(
            os.path.join(self.cleanup_apps_dir, 'proid.app#0000000000001')
        )

    # Disable C0103(Invalid method name)
    # pylint: disable=C0103
    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('treadmill.supervisor.ensure_not_supervised', mock.Mock())
    @mock.patch('treadmill.fs.rm_safe', mock.Mock())
    @mock.patch('treadmill.fs.rmtree_safe', mock.Mock())
    @mock.patch('treadmill.cleanup.Cleanup._refresh_supervisor', mock.Mock())
    def test__remove_cleanup_app_no_link(self):
        """Tests that a cleanup app is removed even if the cleaning link
        has been removed.
        """
        # Access to a protected member _remove_cleanup_app of a client class
        # pylint: disable=W0212
        os.path.exists.side_effect = [False]

        self.cleanup._remove_cleanup_app(
            os.path.join(self.cleanup_dir, 'proid.app#0000000000001'))

        treadmill.fs.rm_safe.assert_not_called()
        treadmill.cleanup.Cleanup._refresh_supervisor.assert_not_called()
        treadmill.supervisor.ensure_not_supervised.assert_not_called()

        treadmill.fs.rmtree_safe.assert_called_with(
            os.path.join(self.cleanup_apps_dir, 'proid.app#0000000000001')
        )

    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('treadmill.supervisor.ensure_not_supervised', mock.Mock())
    @mock.patch('treadmill.fs.rm_safe', mock.Mock())
    @mock.patch('treadmill.fs.rmtree_safe', mock.Mock())
    @mock.patch('treadmill.cleanup.Cleanup._refresh_supervisor', mock.Mock())
    def test__remove_cleanup_app_temp(self):
        """Tests removed cleanup app when link is a temp file.
        """
        # Access to a protected member _remove_cleanup_app of a client class
        # pylint: disable=W0212
        os.path.exists.side_effect = [False]

        self.cleanup._remove_cleanup_app(
            os.path.join(self.cleanup_dir, '.sdfasdfds'))

        treadmill.fs.rm_safe.assert_not_called()
        treadmill.cleanup.Cleanup._refresh_supervisor.assert_not_called()
        treadmill.supervisor.ensure_not_supervised.assert_not_called()
        treadmill.fs.rmtree_safe.assert_not_called()

    @mock.patch('os.readlink', mock.Mock())
    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('treadmill.runtime.get_runtime', mock.Mock(
        return_value=mock.Mock(
            spec_set=treadmill.runtime.runtime_base.RuntimeBase)))
    @mock.patch('treadmill.fs.rm_safe', mock.Mock())
    def test_invoke(self):
        """Tests invoking the cleanup action.
        """
        os.readlink.side_effect = [
            os.path.join(self.cleanup_apps_dir, 'proid.app#0000000000001')
        ]
        os.path.exists.side_effect = [True]

        self.cleanup.invoke('test', 'proid.app#0000000000001')

        mock_runtime = treadmill.runtime.get_runtime(
            'test',
            self.cleanup.tm_env,
            os.path.join(self.cleanup_apps_dir, 'proid.app#0000000000001')
        )
        mock_runtime.finish.assert_called()

        treadmill.fs.rm_safe.assert_called_with(
            os.path.join(self.cleanup_dir, 'proid.app#0000000000001')
        )

    @mock.patch('os.readlink', mock.Mock())
    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('treadmill.runtime.get_runtime', mock.Mock(
        return_value=mock.Mock(
            spec_set=treadmill.runtime.runtime_base.RuntimeBase)))
    @mock.patch('treadmill.fs.rm_safe', mock.Mock())
    def test_invoke_not_exists(self):
        """Tests invoking the cleanup action when the app dir does not exist
        anymore.
        """
        os.readlink.side_effect = [
            os.path.join(self.cleanup_apps_dir, 'proid.app#0000000000001')
        ]
        os.path.exists.side_effect = [False]

        self.cleanup.invoke('test', 'proid.app#0000000000001')

        mock_runtime = treadmill.runtime.get_runtime(
            'test',
            self.cleanup.tm_env,
            os.path.join(self.cleanup_apps_dir, 'proid.app#0000000000001')
        )
        mock_runtime.finish.assert_not_called()

        treadmill.fs.rm_safe.assert_called_with(
            os.path.join(self.cleanup_dir, 'proid.app#0000000000001')
        )

    @mock.patch('os.readlink', mock.Mock())
    @mock.patch('os.path.exists', mock.Mock())
    @mock.patch('shutil.rmtree', mock.Mock())
    @mock.patch('treadmill.runtime.get_runtime', mock.Mock(
        side_effect=supervisor.InvalidServiceDirError
    ))
    @mock.patch('treadmill.fs.rm_safe', mock.Mock())
    def test_invoke_invalid(self):
        """Tests invoking the cleanup action when the app dir is invalid.
        """
        os.readlink.side_effect = [
            os.path.join(self.cleanup_apps_dir, 'proid.app#0000000000001')
        ]
        os.path.exists.side_effect = [True]

        self.cleanup.invoke('test', 'proid.app#0000000000001')

        shutil.rmtree.assert_called_with(
            os.path.join(self.cleanup_apps_dir, 'proid.app#0000000000001')
        )
        treadmill.fs.rm_safe.assert_called_with(
            os.path.join(self.cleanup_dir, 'proid.app#0000000000001')
        )

    @mock.patch('glob.glob', mock.Mock())
    @mock.patch('treadmill.cleanup.Cleanup._add_cleanup_app', mock.Mock())
    @mock.patch('treadmill.cleanup.Cleanup._remove_cleanup_app', mock.Mock())
    def test__sync(self):
        """Tests a full sync of cleanup apps.
        """
        # Access to a protected member _sync of a client class
        # pylint: disable=W0212
        glob.glob.side_effect = [
            [
                os.path.join(self.cleanup_dir, 'proid.app#0000000000002'),
                os.path.join(self.cleanup_dir, 'proid.app#0000000000003')
            ],
            [
                os.path.join(self.cleanup_apps_dir, 'proid.app#0000000000001'),
                os.path.join(self.cleanup_apps_dir, 'proid.app#0000000000002')
            ]
        ]
        self.cleanup._sync()

        treadmill.cleanup.Cleanup._add_cleanup_app.assert_has_calls([
            mock.call('proid.app#0000000000003')
        ])

        treadmill.cleanup.Cleanup._remove_cleanup_app.assert_has_calls([
            mock.call('proid.app#0000000000001')
        ])


if __name__ == '__main__':
    unittest.main()
