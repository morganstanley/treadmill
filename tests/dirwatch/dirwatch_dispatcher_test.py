"""Unit test for treadmill.dirwatch.dirwatch_dispatcher.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

from treadmill import dirwatch


class DirWatchDispatcherTest(unittest.TestCase):
    """Mock test for treadmill.dirwatch.DirWatchDispatcherTest.
    """

    def test_trigger_handler(self):
        """Test handlers."""
        # Access protected module
        # pylint: disable=W0212
        dirwatcher = mock.Mock()
        dispatcher = dirwatch.DirWatcherDispatcher(dirwatcher)

        last_called = set()

        def _created1(_path):
            last_called.add('_created1')

        def _created2(_path):
            last_called.add('_created2')

        def _created3(_path):
            last_called.add('_created3')

        def _modified1(_path):
            last_called.add('_modified1')

        def _modified2(_path):
            last_called.add('_modified2')

        def _deleted1(_path):
            last_called.add('_deleted1')

        dispatcher.register('/path/to/server', {
            dirwatch.DirWatcherEvent.CREATED: _created1,
            dirwatch.DirWatcherEvent.MODIFIED: _modified1,
            dirwatch.DirWatcherEvent.DELETED: _deleted1,
        })

        dispatcher.register('/path/to/placement', {
            dirwatch.DirWatcherEvent.CREATED: _created2,
            dirwatch.DirWatcherEvent.MODIFIED: _modified2,
        })

        dispatcher.register('/path/to/placement/*', {
            dirwatch.DirWatcherEvent.CREATED: _created3,
        })

        dispatcher._on_created('/path/to/server/test')
        self.assertEqual(last_called, set(['_created1']))
        last_called.clear()

        dispatcher._on_modified('/path/to/server/test')
        self.assertEqual(last_called, set(['_modified1']))
        last_called.clear()

        dispatcher._on_deleted('/path/to/server/test')
        self.assertEqual(last_called, set(['_deleted1']))
        last_called.clear()

        dispatcher._on_created('/path/to/placement/test')
        self.assertEqual(last_called, set(['_created2']))
        last_called.clear()

        dispatcher._on_modified('/path/to/placement/test')
        self.assertEqual(last_called, set(['_modified2']))
        last_called.clear()

        dispatcher._on_deleted('/path/to/placement/test')
        self.assertEqual(last_called, set())

        dispatcher._on_created('/path/to/placement/test/one')
        self.assertEqual(last_called, set(['_created3']))
        last_called.clear()


if __name__ == '__main__':
    unittest.main()
