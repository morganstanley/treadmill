"""Unit test for Treadmill rrdutils module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import getopt
import logging
import logging.config
import os
import shutil
import sys
import tempfile
import unittest

import mock

import treadmill
from treadmill import rrdutils

# rrdtool is invalid constant name
# pylint: disable=C0103
rrdtool = '/ms/dist/fsf/PROJ/rrdtool/1.5.6-0/bin/rrdtool'
CMD = ''


def noop(_, in_):
    """Dummy replacement for RRDClient.command() doing almost nothing."""
    # global statement...
    global CMD  # pylint: disable=W0603

    # the verb has to be replaced by the lowercase form
    verb, rest = in_.split(' ', 1)
    CMD = [rrdtool, verb.lower()]
    CMD.extend(rest.split())


class RrdUtilsTest(unittest.TestCase):
    """This contains the treadmill.rrdutils tests."""

    @mock.patch('socket.socket', mock.Mock())
    def setUp(self):
        """Create a temporary file and directory."""
        self.outdir = tempfile.mkdtemp()
        self.rrd_file = os.path.join(self.outdir, 'test.rrd')
        self.rrdclient = rrdutils.RRDClient('/tmp/no_such_socket')

    def tearDown(self):
        """Delete the temporary file and directory."""
        shutil.rmtree(self.outdir, ignore_errors=True)

    @mock.patch('treadmill.subproc.check_output')
    @mock.patch('treadmill.rrdutils.subprocess.check_output')
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
    opts, _ = getopt.getopt(sys.argv[1:], 'l')

    if opts and '-l' in opts[0]:
        sys.argv[1:] = []
        log_conf_file = os.path.join(treadmill.TREADMILL, 'lib', 'python',
                                     'treadmill', 'logging', 'daemon.conf')
        logging.config.fileConfig(log_conf_file)

    unittest.main()
