"""Unit test for treadmill.cron.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

import treadmill
from treadmill.cron import model as cron_model


class CronTest(unittest.TestCase):
    """Tests for teadmill.cron."""

    @mock.patch('treadmill.cron.model.app.create', mock.Mock())
    def test_cron_create(self):
        """Tests cron job create."""
        scheduler = mock.MagicMock()
        cron_model.create(
            scheduler, '1', 'app:create', 'app', 'cron-expression', 3
        )
        treadmill.cron.model.app.create.assert_called_with(
            scheduler, '1', 'app', 'create', 'app', 'cron-expression', 3
        )


if __name__ == '__main__':
    unittest.main()
