"""Unit test Treadmill init."""

import unittest
import mock
import importlib

import treadmill


class TreadmillTest(unittest.TestCase):
    """Test for 'treadmill init'"""

    def test_treadmill_script_for_non_windows(self):
        importlib.reload(treadmill)
        self.assertEqual(treadmill._TREADMILL_SCRIPT, 'treadmill')

    @mock.patch('treadmill.os.name', 'nt')
    def test_treadmill_script_for_windows(self):
        importlib.reload(treadmill)
        self.assertEqual(treadmill._TREADMILL_SCRIPT, 'treadmill.cmd')


if __name__ == '__main__':
    unittest.main()
