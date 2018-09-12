"""Unit test for appcfgmgr - configuring node apps
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import sys
import tempfile
import unittest

import mock

import treadmill
from treadmill import appcfgmgr
from treadmill import fs


class AppCfgMgrTest(unittest.TestCase):
    """Mock test for treadmill.appcfgmgr.AppCfgMgr.
    """

    @mock.patch('treadmill.appenv.AppEnvironment', mock.Mock(autospec=True))
    @mock.patch('treadmill.watchdog.Watchdog', mock.Mock(autospec=True))
    def setUp(self):
        self.root = tempfile.mkdtemp()

        self.cache = os.path.join(self.root, 'cache')
        self.apps = os.path.join(self.root, 'apps')
        self.running = os.path.join(self.root, 'running')
        self.cleanup = os.path.join(self.root, 'cleanup')

        for tmp_dir in [self.cache, self.apps, self.running, self.cleanup]:
            os.mkdir(tmp_dir)

        self.appcfgmgr = appcfgmgr.AppCfgMgr(root=self.root, runtime='linux')
        self.appcfgmgr.tm_env.root = self.root
        self.appcfgmgr.tm_env.cache_dir = self.cache
        self.appcfgmgr.tm_env.apps_dir = self.apps
        self.appcfgmgr.tm_env.running_dir = self.running
        self.appcfgmgr.tm_env.cleanup_dir = self.cleanup

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.appcfg.configure.configure',
                mock.Mock(return_value='/test/foo'))
    @mock.patch('treadmill.fs.symlink_safe', mock.Mock())
    def test__configure(self):
        """Tests application configuration event.
        """
        # Access to a protected member _configure of a client class
        # pylint: disable=W0212

        res = self.appcfgmgr._configure('foo#1')

        treadmill.appcfg.configure.configure.assert_called_with(
            self.appcfgmgr.tm_env,
            os.path.join(self.cache, 'foo#1'),
            'linux'
        )
        treadmill.fs.symlink_safe.assert_called_with(
            os.path.join(self.running, 'foo#1'),
            '/test/foo',
        )
        self.assertTrue(res)

    @mock.patch('treadmill.appcfg.abort.report_aborted', mock.Mock())
    @mock.patch('treadmill.appcfg.configure.configure', mock.Mock())
    @mock.patch('treadmill.fs.rm_safe', mock.Mock())
    def test__configure_exception(self):
        """Tests application configuration exception event.
        """
        # Access to a protected member _configure of a client class
        # pylint: disable=W0212

        treadmill.appcfg.configure.configure.side_effect = Exception('Boom')

        res = self.appcfgmgr._configure('foo#1')

        treadmill.appcfg.abort.report_aborted.assert_called_with(
            self.appcfgmgr.tm_env,
            'foo#1',
            why=treadmill.appcfg.abort.AbortedReason.UNKNOWN,
            payload=mock.ANY,
        )
        treadmill.fs.rm_safe.assert_called_with(
            os.path.join(self.cache, 'foo#1')
        )
        self.assertFalse(res)

    @mock.patch('treadmill.appcfg.abort.report_aborted', mock.Mock())
    @mock.patch('treadmill.appcfg.configure.configure', mock.Mock())
    @mock.patch('treadmill.fs.rm_safe', mock.Mock())
    def test__configure_failure(self):
        """Tests application configuration failure event.
        """
        # Access to a protected member _configure of a client class
        # pylint: disable=W0212

        treadmill.appcfg.configure.configure.return_value = None

        res = self.appcfgmgr._configure('foo#1')

        treadmill.appcfg.abort.report_aborted.assert_not_called()
        treadmill.fs.rm_safe.assert_called_with(
            os.path.join(self.cache, 'foo#1')
        )
        self.assertFalse(res)

    # FIXME: windows does not support symlink for non-privlege user
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/treadmill'))
    def test__terminate(self):
        """Tests terminate removes /running links.
        """
        # Access to a protected member _terminate of a client class
        # pylint: disable=W0212

        fs.mkdir_safe(os.path.join(self.apps, 'proid.app-0-1234', 'data'))
        os.symlink(
            os.path.join(self.apps, 'proid.app-0-1234'),
            os.path.join(self.running, 'proid.app#0'),
        )

        self.appcfgmgr._terminate('proid.app#0')

        self.assertFalse(
            os.path.exists(os.path.join(self.running, 'proid.app#0'))
        )
        self.assertEqual(
            os.readlink(os.path.join(self.cleanup, 'proid.app-0-1234')),
            os.path.join(self.apps, 'proid.app-0-1234')
        )
        self.assertTrue(
            os.path.exists(
                os.path.join(
                    self.apps, 'proid.app-0-1234', 'data', 'terminated'
                )
            )
        )

    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._configure', mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor',
                mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._terminate', mock.Mock())
    @mock.patch('treadmill.appcfg.eventfile_unique_name', mock.Mock())
    def test__synchronize_noop(self):
        """Tests synchronize when there is nothing to do.
        """
        # Access to a protected member _synchronize of a client class
        # pylint: disable=W0212
        def _fake_unique_name(name):
            """Fake container unique name function.
            """
            uniquename = os.path.basename(name)
            uniquename = uniquename.replace('#', '-')
            uniquename += '-1234'
            return uniquename
        treadmill.appcfg.eventfile_unique_name.side_effect = _fake_unique_name
        for app in ('proid.app#0', 'proid.app#1', 'proid.app#2'):
            # Create cache/ entry
            with io.open(os.path.join(self.cache, app), 'w'):
                pass
            # Create app/ dir
            uniquename = _fake_unique_name(app)
            os.mkdir(os.path.join(self.apps, uniquename))

        self.appcfgmgr._synchronize()

        treadmill.appcfgmgr.AppCfgMgr._terminate.assert_not_called()
        # We always configure
        treadmill.appcfgmgr.AppCfgMgr._configure.assert_has_calls(
            [
                mock.call('proid.app#0'),
                mock.call('proid.app#1'),
                mock.call('proid.app#2'),
            ],
            any_order=True
        )
        treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor.assert_called()

    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._configure', mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor',
                mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._terminate', mock.Mock())
    @mock.patch('treadmill.appcfg.eventfile_unique_name', mock.Mock())
    def test__synchronize_config(self):
        """Tests synchronize when there are apps to configure.
        """
        # Access to a protected member _synchronize of a client class
        # pylint: disable=W0212

        def _fake_unique_name(name):
            """Fake container unique name function.
            """
            uniquename = os.path.basename(name)
            uniquename = uniquename.replace('#', '-')
            uniquename += '-1234'
            return uniquename
        treadmill.appcfg.eventfile_unique_name.side_effect = _fake_unique_name
        for app in ('proid.app#0', 'proid.app#1', 'proid.app#2'):
            # Create cache/ entry
            with io.open(os.path.join(self.cache, app), 'w'):
                pass
            uniquename = _fake_unique_name(app)
            os.mkdir(os.path.join(self.apps, uniquename))

        self.appcfgmgr._synchronize()

        treadmill.appcfgmgr.AppCfgMgr._configure.assert_has_calls(
            [
                mock.call('proid.app#0'),
                mock.call('proid.app#1'),
                mock.call('proid.app#2')
            ],
            any_order=True,
        )
        treadmill.appcfgmgr.AppCfgMgr._terminate.assert_not_called()
        treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor.assert_called()

    # FIXME: windows does not support symlink for non-privlege user
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('treadmill.fs.symlink_safe', mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._configure', mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._terminate', mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor',
                mock.Mock())
    @mock.patch('treadmill.appcfg.eventfile_unique_name', mock.Mock())
    def test__synchronize_term(self):
        """Tests synchronize when there are apps to terminate.
        """
        # Access to a protected member _synchronize of a client class
        # pylint: disable=W0212
        def _fake_unique_name(name):
            """Fake container unique name function.
            """
            uniquename = os.path.basename(name)
            uniquename = uniquename.replace('#', '-')
            uniquename += '-1234'
            return uniquename
        treadmill.appcfg.eventfile_unique_name.side_effect = _fake_unique_name

        for app in ('proid.app#0', 'proid.app#1', 'proid.app#2'):
            # Create cache/ entry
            with io.open(os.path.join(self.cache, app), 'w') as _f:
                pass
            # Create app/ dir
            uniquename = _fake_unique_name(app)
            app_dir = os.path.join(self.apps, uniquename)
            os.mkdir(app_dir)
            # Create exitinfo file in data dir
            data_dir = os.path.join(app_dir, 'data')
            os.mkdir(data_dir)
            with io.open(os.path.join(data_dir, 'exitinfo'), 'w') as _f:
                pass

        self.appcfgmgr._synchronize()

        treadmill.appcfgmgr.AppCfgMgr._configure.assert_not_called()
        treadmill.appcfgmgr.AppCfgMgr._terminate.assert_not_called()
        treadmill.fs.symlink_safe.assert_has_calls(
            [
                mock.call(
                    os.path.join(self.cleanup, 'proid.app#0'),
                    os.path.join(self.apps, _fake_unique_name('proid.app#0')),
                ),
                mock.call(
                    os.path.join(self.cleanup, 'proid.app#1'),
                    os.path.join(self.apps, _fake_unique_name('proid.app#1')),
                ),
                mock.call(
                    os.path.join(self.cleanup, 'proid.app#2'),
                    os.path.join(self.apps, _fake_unique_name('proid.app#2')),
                ),
            ],
            any_order=True,
        )
        treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor.assert_called()

    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._configure', mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor',
                mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._terminate', mock.Mock())
    @mock.patch('treadmill.appcfg.eventfile_unique_name', mock.Mock())
    def test__synchronize_with_files(self):
        """Tests that sync leaves files that are not symlinks as is.
        """
        # Access to a protected member _synchronize of a client class
        # pylint: disable=W0212

        with io.open(os.path.join(self.running, 'xxx'), 'w'):
            pass

        self.appcfgmgr._synchronize()

        # xxx shouldn't have been touched.
        self.assertTrue(os.path.exists(os.path.join(self.running, 'xxx')))
        treadmill.appcfgmgr.AppCfgMgr._terminate.assert_not_called()
        treadmill.appcfgmgr.AppCfgMgr._configure.assert_not_called()
        treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor.assert_called()

    # FIXME: windows does not support symlink for non-privlege user
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._configure', mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor',
                mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._terminate', mock.Mock())
    @mock.patch('treadmill.appcfg.eventfile_unique_name', mock.Mock())
    def test__synchronize_broken_link(self):
        """Tests that sync cleans up broken symlinks.
        """
        # Access to a protected member _synchronize of a client class
        # pylint: disable=W0212

        def _fake_unique_name(name):
            """Fake container unique name function.
            """
            uniquename = os.path.basename(name)
            uniquename = uniquename.replace('#', '-')
            uniquename += '-1234'
            return uniquename
        treadmill.appcfg.eventfile_unique_name.side_effect = _fake_unique_name
        # Create cache/ entry
        with io.open(os.path.join(self.cache, 'foo#1'), 'w'):
            pass
        # Create a broken running/ symlink
        os.symlink(os.path.join(self.apps, 'foo-1-1234'),
                   os.path.join(self.running, 'foo#1'))

        self.appcfgmgr._synchronize()

        treadmill.appcfgmgr.AppCfgMgr._terminate.assert_not_called()
        treadmill.appcfgmgr.AppCfgMgr._configure.assert_called_with(
            'foo#1'
        )
        treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor.assert_called()

    # FIXME: windows does not support symlink for non-privlege user
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._configure', mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor',
                mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._terminate', mock.Mock())
    @mock.patch('treadmill.appcfg.eventfile_unique_name', mock.Mock())
    def test__synchronize_running_link(self):
        """Tests that sync ignores configured apps that are running.
        """
        # Access to a protected member _synchronize of a client class
        # pylint: disable=W0212

        def _fake_unique_name(name):
            """Fake container unique name function.
            """
            uniquename = os.path.basename(name)
            uniquename = uniquename.replace('#', '-')
            uniquename += '-1234'
            return uniquename
        treadmill.appcfg.eventfile_unique_name.side_effect = _fake_unique_name

        # Create app name
        uniquename = _fake_unique_name('proid.foo#1')
        app_dir = os.path.join(self.apps, uniquename)
        os.mkdir(app_dir)

        # Create cache/ entry
        with io.open(os.path.join(self.cache, 'proid.foo#1'), 'w') as _f:
            pass

        # Create a running/ symlink
        os.symlink(os.path.join(self.apps, 'proid.foo-1-1234'),
                   os.path.join(self.running, 'proid.foo#1'))

        self.appcfgmgr._synchronize()

        treadmill.appcfgmgr.AppCfgMgr._terminate.assert_not_called()
        treadmill.appcfgmgr.AppCfgMgr._configure.assert_not_called()
        treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor.assert_called()

    # Disable C0103(invalid-name)
    # pylint: disable=C0103
    # FIXME: windows does not support symlink for non-privlege user
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._configure', mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor',
                mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._terminate', mock.Mock())
    @mock.patch('treadmill.appcfg.eventfile_unique_name', mock.Mock())
    def test__synchronize_running_no_cache_link(self):
        """Tests that sync terminates running apps that are not in cache.
        """
        # Access to a protected member _synchronize of a client class
        # pylint: disable=W0212

        def _fake_unique_name(name):
            """Fake container unique name function.
            """
            uniquename = os.path.basename(name)
            uniquename = uniquename.replace('#', '-')
            uniquename += '-1234'
            return uniquename
        treadmill.appcfg.eventfile_unique_name.side_effect = _fake_unique_name

        # Create app name
        uniquename = _fake_unique_name('proid.foo#1')
        app_dir = os.path.join(self.apps, uniquename)
        os.mkdir(app_dir)

        # Create a running/ symlink
        os.symlink(os.path.join(self.apps, 'proid.foo-1-1234'),
                   os.path.join(self.running, 'proid.foo#1'))

        self.appcfgmgr._synchronize()

        treadmill.appcfgmgr.AppCfgMgr._terminate.assert_called_with(
            'proid.foo#1')
        treadmill.appcfgmgr.AppCfgMgr._configure.assert_not_called()
        treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor.assert_called()

    # FIXME: windows does not support symlink for non-privlege user
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._configure', mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor',
                mock.Mock())
    @mock.patch('treadmill.appcfgmgr.AppCfgMgr._terminate', mock.Mock())
    @mock.patch('treadmill.appcfg.eventfile_unique_name', mock.Mock())
    def test__synchronize_cleanup_link(self):
        """Tests that sync ignores configured apps that are being cleaned up.
        """
        # Access to a protected member _synchronize of a client class
        # pylint: disable=W0212

        def _fake_unique_name(name):
            """Fake container unique name function.
            """
            uniquename = os.path.basename(name)
            uniquename = uniquename.replace('#', '-')
            uniquename += '-1234'
            return uniquename
        treadmill.appcfg.eventfile_unique_name.side_effect = _fake_unique_name

        # Create app name
        uniquename = _fake_unique_name('proid.foo#1')
        app_dir = os.path.join(self.apps, uniquename)
        os.mkdir(app_dir)

        # Create cache/ entry
        with io.open(os.path.join(self.cache, 'proid.foo#1'), 'w') as _f:
            pass

        # Create a running/ symlink
        os.symlink(os.path.join(self.apps, 'proid.foo-1-1234'),
                   os.path.join(self.cleanup, 'proid.foo#1'))

        self.appcfgmgr._synchronize()

        treadmill.appcfgmgr.AppCfgMgr._terminate.assert_not_called()
        treadmill.appcfgmgr.AppCfgMgr._configure.assert_not_called()
        treadmill.appcfgmgr.AppCfgMgr._refresh_supervisor.assert_called()

    @mock.patch('treadmill.supervisor.control_svscan', mock.Mock())
    def test__refresh_supervisor(self):
        """Check how the supervisor is being refreshed.
        """
        # Access to a protected member _refresh_supervisor of a client class
        # pylint: disable=W0212

        self.appcfgmgr._refresh_supervisor()

        treadmill.supervisor.control_svscan.assert_called_with(
            self.running, (
                treadmill.supervisor.SvscanControlAction.alarm,
                treadmill.supervisor.SvscanControlAction.nuke
            )
        )


if __name__ == '__main__':
    unittest.main()
