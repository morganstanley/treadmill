"""
Unit test for Treadmill rrdutils module.
"""

import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

from treadmill import rrdutils


class RrdUtilsTest(unittest.TestCase):
    """This contains the treadmill.rrdutils tests."""

    @mock.patch('treadmill.subproc.check_output')
    @mock.patch('subprocess.check_output')
    def test_first(self, subprocess_mock, subproc_mock):
        """Test the function that returns the first ts in the designated RRA.
        """
        rrdutils.first('foo.rrd')
        subproc_mock.assert_called_with(
            [rrdutils.RRDTOOL, 'first', 'foo.rrd', '--daemon', 'unix:%s' %
             rrdutils.SOCKET, '--rraindex', rrdutils.SHORT_TERM_RRA_IDX])

        rrdutils.first('foo.rrd',
                       exec_on_node=False,
                       rra_idx=rrdutils.LONG_TERM_RRA_IDX)
        subprocess_mock.assert_called_with(
            [rrdutils.RRDTOOL, 'first', 'foo.rrd', '--rraindex',
             rrdutils.LONG_TERM_RRA_IDX])


if __name__ == '__main__':
    unittest.main()
