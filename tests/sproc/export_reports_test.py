"""Unit tests for treadmill.sproc.export_reports.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import bz2
import unittest

import mock

from treadmill.sproc.export_reports import export_reports


class ExportReportsTest(unittest.TestCase):
    """Test treadmill.sproc.export_reports."""

    # 1483228800 is 2017-01-01T00:00:00Z
    @mock.patch('time.time', mock.Mock(return_value=1483228800))
    @mock.patch('bz2.BZ2File', mock.mock_open())
    def test_export_reports(self):
        """Test saving of state reports to file."""
        zkclient = mock.Mock()
        zkclient.get_children.return_value = ['foo']
        zkclient.get.return_value = ('save this', 'meta')

        mock_handle = bz2.BZ2File.return_value

        cell_dir = '/foo/bar'
        export_reports(cell_dir, zkclient)

        zkclient.get.assert_called_with('/reports/foo')
        mock_handle.write.assert_called_with('save this')

        # Ensure filenames are in UTC timezone
        bz2.BZ2File.assert_called_with(
            '/foo/bar/2017-01-01T00:00:00_foo.csv.bz2',
            'w'
        )


if __name__ == '__main__':
    unittest.main()
