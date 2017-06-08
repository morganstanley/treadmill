"""Unit test for Treadmill rrdutils module.
"""

import unittest

import mock

from treadmill import rrdutils


class RrdUtilsTest(unittest.TestCase):
    """This contains the treadmill.rrdutils tests."""

    @mock.patch('treadmill.subproc.check_output')
    @mock.patch('subprocess.check_output')
    def test_first(self, subprocess_mock, subproc_mock):
        """Test the function that returns the first ts in the designated RRA.
        """
        rrdutils.first('foo.rrd', 'no_such_timeframe')
        subproc_mock.assert_called_with(
            [rrdutils.RRDTOOL, 'first', 'foo.rrd', '--daemon',
             'unix:%s' % rrdutils.SOCKET, '--rraindex',
             rrdutils.TIMEFRAME_TO_RRA_IDX['short']])

        rrdutils.first('foo.rrd', 'long', exec_on_node=False)
        subprocess_mock.assert_called_with(
            [rrdutils.RRDTOOL, 'first', 'foo.rrd', '--rraindex',
             rrdutils.TIMEFRAME_TO_RRA_IDX['long']])


if __name__ == '__main__':
    unittest.main()
