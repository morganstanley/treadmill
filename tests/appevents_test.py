"""
Unit test for appevents.
"""

import os
import shutil
import tempfile
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

from treadmill import appevents
from treadmill.apptrace import events


class AppeventsTest(unittest.TestCase):
    """Tests for teadmill.fs."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('time.time', mock.Mock(return_value=100))
    def test_post(self):
        """Test appevents.post."""
        appevents.post(
            self.root,
            events.AbortedTraceEvent(
                why='container_error',
                instanceid='foo.bar#123',
                payload=None
            )
        )
        self.assertTrue(os.path.exists(
            os.path.join(self.root,
                         '100,foo.bar#123,aborted,container_error')))


if __name__ == '__main__':
    unittest.main()
