"""Unit tests for treadmill.alert.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import tempfile
import os.path
import unittest

import mock
from treadmill import alert


class TestBasics(unittest.TestCase):
    """Unit tests for treadmill.alert.
    """

    # Disable W0212: accessing protected members
    # pylint: disable=W0212
    @mock.patch('treadmill.alert._to_filename', return_value='test.file')
    def test_create_read(self, _):
        """Test alert.create() and alert.read().
        """
        # no epoch_ts defined
        alert_ = dict(
            type_='test',
            summary='test summary',
            instanceid='testorigin',
            foo='bar'
        )

        with tempfile.TemporaryDirectory() as alerts_dir, \
                mock.patch('time.time', return_value=987.654):
            alert.create(alerts_dir, **alert_)
            alert_file = os.path.join(
                alerts_dir,
                alert._to_filename(alert_['instanceid'], alert_['type_'])
            )

            self.assertTrue(os.path.exists(alert_file))

            # epoch_ts was None
            alert_['epoch_ts'] = 987.654
            self.assertEqual(alert_, alert.read(alert_file))

            # check whether epoch_ts is preserved if passed to create()
            alert_['epoch_ts'] = 1.2
            alert.create(alerts_dir, **alert_)
            self.assertEqual(alert_, alert.read(alert_file))

    def test_to_filename(self):
        """test alert._to_filename().
        """
        with mock.patch('time.monotonic', return_value=123.456):
            self.assertEqual(
                alert._to_filename(instanceid='origin', type_='type'),
                '123.456000-origin-type'
            )
            # make sure that filename is not interpreted as a directory
            # even if / (unix) or \ (win) is among the parts constructing it
            self.assertEqual(
                alert._to_filename(
                    instanceid=os.path.join('cell', 'blah'),
                    type_=os.path.join('ty', 'pe')
                ),
                '123.456000-cell_blah-ty_pe'
            )


if __name__ == '__main__':
    unittest.main()
