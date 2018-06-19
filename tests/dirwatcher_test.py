"""Unit test for directory watcher.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import io
import os
import shutil
import sys
import tempfile
import unittest

if os.name != 'nt':
    import select

import mock

from treadmill import dirwatch


class DirWatcherTest(unittest.TestCase):
    """Tests for teadmill.dirwatch."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_watcher(self):
        """Tests created/deleted callbacks."""
        created = set()
        modified = set()
        deleted = set()
        test_file = os.path.join(self.root, 'a')

        watcher = dirwatch.DirWatcher(self.root)
        watcher.on_created = lambda x: created.add(x) or 'one'
        watcher.on_modified = lambda x: modified.add(x) or 'two'
        watcher.on_deleted = lambda x: deleted.add(x) or 'three'

        self.assertFalse(watcher.wait_for_events(0))

        with io.open(test_file, 'w') as f:
            f.write('hello')
        with io.open(test_file, 'a') as f:
            f.write(' world!')
        os.unlink(test_file)
        with io.open(test_file, 'w') as f:
            f.write('hello again')

        if sys.platform.startswith('linux'):
            res = watcher.process_events(max_events=3)
        else:
            self.assertTrue(watcher.wait_for_events(0))
            self.assertTrue(watcher.wait_for_events(0))
            res = watcher.process_events(max_events=4)

        self.assertEqual({test_file}, created)
        self.assertEqual({test_file}, modified)
        self.assertEqual({test_file}, deleted)

        if sys.platform.startswith('linux'):
            self.assertEqual(
                [
                    (dirwatch.DirWatcherEvent.CREATED, test_file, 'one'),
                    (dirwatch.DirWatcherEvent.MODIFIED, test_file, 'two'),
                    (dirwatch.DirWatcherEvent.DELETED, test_file, 'three'),
                    (dirwatch.DirWatcherEvent.MORE_PENDING, None, None),
                ],
                res,
            )
        else:
            self.assertEqual(
                [
                    (dirwatch.DirWatcherEvent.CREATED, test_file, 'one'),
                    (dirwatch.DirWatcherEvent.MODIFIED, test_file, 'two'),
                    (dirwatch.DirWatcherEvent.MODIFIED, test_file, 'two'),
                    (dirwatch.DirWatcherEvent.DELETED, test_file, 'three'),
                    (dirwatch.DirWatcherEvent.MORE_PENDING, None, None),
                ],
                res,
            )

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Requires Linux')
    @mock.patch('select.poll', mock.Mock())
    def test_signal(self):
        """Tests behavior when signalled during wait."""
        watcher = dirwatch.DirWatcher(self.root)

        mocked_pollobj = select.poll.return_value
        mocked_pollobj.poll.side_effect = select.error(errno.EINTR, '')

        self.assertFalse(watcher.wait_for_events())


if __name__ == '__main__':
    unittest.main()
