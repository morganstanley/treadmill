"""Unit test for directory watcher (inotify).
"""

import errno
import os
import shutil
import tempfile
import select
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

from treadmill import idirwatch


class DirWatcherTest(unittest.TestCase):
    """Tests for teadmill.idirwatch."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_watcher(self):
        """Tests created/deleted callbackes."""
        created = []
        modified = []
        deleted = []
        test_file = os.path.join(self.root, 'a')

        watcher = idirwatch.DirWatcher(self.root)
        watcher.on_created = lambda x: created.append(x) or 'one'
        watcher.on_modified = lambda x: modified.append(x) or 'two'
        watcher.on_deleted = lambda x: deleted.append(x) or 'three'

        with open(test_file, 'w') as f:
            f.write('hello')
        with open(test_file, 'a') as f:
            f.write(' world!')
        os.unlink(test_file)
        with open(test_file, 'w') as f:
            f.write('hello again')

        res = watcher.process_events(max_events=3)

        self.assertEqual([test_file], created)
        self.assertEqual([test_file], modified)
        self.assertEqual([test_file], deleted)
        self.assertEqual(
            [
                (idirwatch.DirWatcherEvent.CREATED, test_file, 'one'),
                (idirwatch.DirWatcherEvent.MODIFIED, test_file, 'two'),
                (idirwatch.DirWatcherEvent.DELETED, test_file, 'three'),
                (idirwatch.DirWatcherEvent.MORE_PENDING, None, None),
            ],
            res,
        )

    @mock.patch('select.poll', mock.Mock())
    def test_signal(self):
        """Tests behavior when signalled during wait."""
        watcher = idirwatch.DirWatcher(self.root)

        mocked_pollobj = select.poll.return_value
        mocked_pollobj.poll.side_effect = select.error(errno.EINTR, '')

        self.assertFalse(watcher.wait_for_events())


if __name__ == '__main__':
    unittest.main()
