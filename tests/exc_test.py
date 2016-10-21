"""Unit test for treadmill.exc.
"""

import unittest

import mock

import treadmill
from treadmill import exc


class ExcTest(unittest.TestCase):
    """Tests for teadmill.exc."""

    @mock.patch('treadmill.utils.sys_exit', mock.Mock())
    def test_decorator_tm_exc(self):
        """Test the `exit_on_unhandled` decorator on `TreadmillError`."""
        @exc.exit_on_unhandled
        def test_fun():
            """raise exc.TreadmillError('test')."""
            raise exc.TreadmillError('test')

        test_fun()

        treadmill.utils.sys_exit.assert_called_with(-1)

    @mock.patch('treadmill.utils.sys_exit', mock.Mock())
    def test_decorator_py_exc(self):
        """Test the `exit_on_unhandled` decorator on Python `Exception`."""
        @exc.exit_on_unhandled
        def test_fun():
            """raise Exception('test')."""
            raise Exception('test')

        test_fun()

        treadmill.utils.sys_exit.assert_called_with(-1)


if __name__ == '__main__':
    unittest.main()
