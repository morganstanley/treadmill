"""Scheduler reports API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import bz2
import unittest

import mock
import pandas as pd

from treadmill.api import scheduler  # pylint: disable=no-name-in-module


class ApiReportTest(unittest.TestCase):
    """treadmill.api.report tests.
    """

    def setUp(self):
        self.report = scheduler.API()

    @mock.patch('treadmill.context.ZkContext.conn')
    def test_get(self, zk_mock):
        """Test fetching a report.
        """
        content = '\n'.join([
            'a,b,c',
            '1,2,3',
            '4,5,6'
        ])
        zk_mock.get.return_value = (bz2.compress(content.encode()), None)

        result = self.report.get('foo')

        zk_mock.get.assert_called_with('/reports/foo')
        pd.util.testing.assert_frame_equal(
            result,
            pd.DataFrame([[1, 2, 3], [4, 5, 6]], columns=['a', 'b', 'c'])
        )

    @mock.patch('treadmill.context.ZkContext.conn')
    def test_get_match(self, zk_mock):
        """Test match parameter on get csv.
        """
        zk_mock.get_children.return_value = ['apps', 'allocations', 'servers']
        content = '\n'.join([
            'instance,allocation,rank',
            'findme,foo,2',
            'findmetoo,bar,3',
            'andthenfindme,foo,4'
        ])
        zk_mock.get.return_value = (bz2.compress(content.encode()), None)
        result = self.report.get('apps', match='findme')
        zk_mock.get.assert_called_with('/reports/apps')
        pd.util.testing.assert_frame_equal(
            result,
            pd.DataFrame(
                [['findme', 'foo', 2]],
                columns=['instance', 'allocation', 'rank']
            )
        )
        result = self.report.get('apps', match='findme*')
        zk_mock.get.assert_called_with('/reports/apps')
        pd.util.testing.assert_frame_equal(
            result,
            pd.DataFrame(
                [['findme', 'foo', 2], ['findmetoo', 'bar', 3]],
                columns=['instance', 'allocation', 'rank']
            )
        )
        result = self.report.get('apps', match='*findme')
        zk_mock.get.assert_called_with('/reports/apps')
        pd.util.testing.assert_frame_equal(
            result,
            pd.DataFrame(
                [['findme', 'foo', 2], ['andthenfindme', 'foo', 4]],
                columns=['instance', 'allocation', 'rank']
            )
        )

    @mock.patch('treadmill.context.ZkContext.conn')
    def test_get_partition(self, zk_mock):
        """Test partition parameter on get csv.
        """
        zk_mock.get_children.return_value = ['apps', 'allocations', 'servers']
        content = '\n'.join([
            'instance,allocation,rank,partition',
            'findme,foo,2,part1',
            'findmetoo,bar,3,part1',
            'andthenfindme,foo,4,part2',
            'foobar,foo,4,part3',
        ])
        zk_mock.get.return_value = (bz2.compress(content.encode()), None)
        result = self.report.get('apps', partition='part1')

        zk_mock.get.assert_called_with('/reports/apps')
        pd.util.testing.assert_frame_equal(
            result,
            pd.DataFrame(
                [
                    ['findme', 'foo', 2, 'part1'],
                    ['findmetoo', 'bar', 3, 'part1'],
                ],
                columns=['instance', 'allocation', 'rank', 'partition']
            )
        )

        result = self.report.get('apps', partition='part[12]')
        zk_mock.get.assert_called_with('/reports/apps')
        pd.util.testing.assert_frame_equal(
            result,
            pd.DataFrame(
                [
                    ['findme', 'foo', 2, 'part1'],
                    ['findmetoo', 'bar', 3, 'part1'],
                    ['andthenfindme', 'foo', 4, 'part2'],
                ],
                columns=['instance', 'allocation', 'rank', 'partition']
            )
        )

        result = self.report.get('apps', partition='*part1')
        zk_mock.get.assert_called_with('/reports/apps')
        pd.util.testing.assert_frame_equal(
            result,
            pd.DataFrame(
                [
                    ['findme', 'foo', 2, 'part1'],
                    ['findmetoo', 'bar', 3, 'part1'],
                ],
                columns=['instance', 'allocation', 'rank', 'partition']
            )
        )


if __name__ == '__main__':
    unittest.main()
