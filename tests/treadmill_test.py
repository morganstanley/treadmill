"""Unit test Treadmill init."""

import unittest
import mock
import os
import treadmill
import importlib
from treadmill.cli.aws import deploy_path_join


class TreadmillTest(unittest.TestCase):
    """Test for 'treadmill init'"""

    def test_treadmill_script_for_non_windows(self):
        importlib.reload(treadmill)

        self.assertEqual(treadmill._TREADMILL_SCRIPT, 'treadmill')

    @mock.patch('treadmill.os.name', 'nt')
    def test_treadmill_script_for_windows(self):
        importlib.reload(treadmill)

        self.assertEqual(treadmill._TREADMILL_SCRIPT, 'treadmill.cmd')

    @mock.patch('treadmill.os.environ.get',
                mock.Mock(return_value='/foo/bar/env'))
    def test_treadmill_root_and_bin_with_virtual_env(self):
        importlib.reload(treadmill)

        treadmill.os.environ.get.assert_any_call('VIRTUAL_ENV')
        self.assertEqual(treadmill.TREADMILL_BIN, '/foo/bar/env/bin/treadmill')
        self.assertEqual(treadmill.TREADMILL, treadmill.__path__[0] + '/../')

    @mock.patch('treadmill.os.environ.get', mock.Mock(return_value=None))
    def test_treadmill_root_and_bin_without_virtual_env(self):
        importlib.reload(treadmill)

        treadmill.os.environ.get.assert_any_call('VIRTUAL_ENV')
        self.assertEqual(treadmill.TREADMILL_BIN, '/bin/treadmill')
        self.assertEqual(
            treadmill.TREADMILL,
            os.path.realpath(os.path.dirname(__file__) + '/..')
        )

    @mock.patch('treadmill.os.environ.get',
                mock.Mock(return_value='ldap_connection'))
    def test_treadmill_ldap(self):
        importlib.reload(treadmill)

        treadmill.os.environ.get.assert_any_call('TREADMILL_LDAP')
        self.assertEqual(treadmill.TREADMILL_LDAP, 'ldap_connection')

    def test_treadmill_deploy_package(self):
        self.assertTrue('/deploy/' in treadmill.TREADMILL_DEPLOY_PACKAGE)
        self.assertTrue(os.path.exists(treadmill.TREADMILL_DEPLOY_PACKAGE))

    def test_treadmill_exe_whitelist_exists(self):
        importlib.reload(treadmill)
        self.assertIsNotNone(os.environ.get('TREADMILL_EXE_WHITELIST'))

    @mock.patch('treadmill.cli.os.path.exists')
    def test_deploy_path_join(self, exists_mock):
        """Test deploy path"""
        exists_mock.return_value = True
        self.assertEquals(
            os.path.realpath(os.path.realpath('deploy')),
            deploy_path_join('../deploy')
        )

        exists_mock.return_value = False
        self.assertEquals(
            os.path.realpath(treadmill.TREADMILL_DEPLOY_PACKAGE + '../deploy'),
            deploy_path_join('../deploy')
        )


if __name__ == '__main__':
    unittest.main()
