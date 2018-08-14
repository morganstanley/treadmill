"""Unit tests for treadmill.sproc.export_reports.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill.sproc.export_reports import export_reports


class ExportReportsTest(unittest.TestCase):
    """Test treadmill.sproc.export_reports."""

    # 1483228800 is 2017-01-01T00:00:00Z
    @mock.patch('time.time', mock.Mock(return_value=1483228800))
    @mock.patch('io.open', mock.mock_open(), create=True)
    def test_export_reports(self):
        """Test saving of state reports to file."""
        zkclient = mock.Mock()
        zkclient.get_children.return_value = ['foo']
        zkclient.get.return_value = ('save this', 'meta')

        cell_dir = '/foo/bar'

        export_reports(cell_dir, zkclient)

        # Ensure filenames are in UTC timezone
        io.open.assert_called_with(
            '/foo/bar/2017-01-01T00:00:00_foo.csv.bz2',
            'wb'
        )

        zkclient.get.assert_called_with('/reports/foo')
        io.open().write.assert_called_with('save this')


if __name__ == '__main__':
    unittest.main()
