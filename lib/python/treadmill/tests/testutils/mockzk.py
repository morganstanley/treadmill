"""Mock Zookeeper TestCase.

Usage::

  class MyTest(MockZookeeperTestCase):

      @mock.patch('zookeeper.get', mock.Mock())
      @mock.patch('zookeeper.get_children', mock.Mock())
      def test_some_zk_ops(self):
          zkdata = {
            'foo': {
                'bar': '123'
            }
          }

          self.make_mock_zk(zkdata)

          # call funcs that will call zookeeper.get / get_children
          zkdata['foo']['bla'] = '456'

          # The watcher will be invoked, and get_children will return
          # ['bla', 'bar']
          self.notify(zookeeper.CHILD_EVENT, '/foo')

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import copy
import threading
import time
import unittest

from collections import namedtuple

import kazoo
from kazoo.protocol import states
from six.moves import queue

from treadmill import yamlwrapper as yaml


class MockZookeeperMetadata(namedtuple('MockZookeeperMetadata',
                                       ['czxid',
                                        'ctime',
                                        'mzxid',
                                        'mtime',
                                        'ephemeralOwner',
                                        'children_count'])):
    """Subset of the Zookeeper metadata we are using."""

    # namedtuple classes dont have an __init__, that's ok
    # Use ephemeralOwner as that is the name in the real Zookeeper metadata
    # object
    # pylint: disable=W0232,C0103

    _BASE_ZXID = int(time.time())

    @property
    def creation_transaction_id(self):
        """creation_transaction_id getter."""
        return self.czxid

    @property
    def last_modified_transaction_id(self):
        """last_modified_transaction_id getter."""
        return self.mzxid

    @property
    def created(self):
        """created getter."""
        return self.ctime / 100.0

    @property
    def last_modified(self):
        """last_modified getter."""
        return self.mtime / 100.0

    @classmethod
    def from_dict(cls, value_dict):
        """Create a Metadata instance from dict values."""
        curr_time = time.time()
        zxid = int(cls._BASE_ZXID + curr_time)
        timestamp_ms = int(curr_time * 100)

        ctime = value_dict.get('ctime', timestamp_ms)
        czxid = value_dict.get('czxid', zxid)
        mtime = value_dict.get('mtime', timestamp_ms)
        mzxid = value_dict.get('mzxid', zxid)
        children_count = value_dict.get('children_count', 0)
        ephemeralOwner = value_dict.get('ephemeralOwner', 0)

        if 'creation_transaction_id' in value_dict:
            czxid = value_dict['creation_transaction_id']
        if 'created' in value_dict:
            ctime = int(value_dict['created'] * 100)
        if 'last_modified_transaction_id' in value_dict:
            mzxid = value_dict['last_modified_transaction_id']
        if 'last_modified' in value_dict:
            mtime = int(value_dict['last_modified'] * 100)

        return cls(ctime=ctime, czxid=czxid, mtime=mtime, mzxid=mzxid,
                   ephemeralOwner=ephemeralOwner,
                   children_count=children_count)


class MockZookeeperTestCase(unittest.TestCase):
    """Helper class to mock Zk get[children] events."""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912

    def setUp(self):
        super(MockZookeeperTestCase, self).setUp()
        self.watch_events = None

    def tearDown(self):
        """Send terminate signal to mock Zk events thread."""
        if self.watch_events:
            self.watch_events.put('exit')

    def make_mock_zk(self, zk_content, events=False):
        """Constructs zk mock implementation of get based on dictionary.

        Treats dictionary as tree structure, mapping it into mock Zk instance.
        """
        # pylint: disable=too-many-statements
        watches = {}

        def mock_exists(zkpath, watch=None):
            """Mocks node exists."""
            del watch
            # TODO: support watch.
            path = zkpath.split('/')
            path.pop(0)
            content = zk_content

            while path:
                path_component = path.pop(0)
                if path_component not in content:
                    return False

                content = content[path_component]

            return True

        def mock_delete(zkpath, recursive=False):
            """Mocks node deletion."""
            del recursive

            path = zkpath.split('/')
            path.pop(0)
            last = path.pop(-1)
            content = zk_content
            while path:
                path_component = path.pop(0)
                if path_component not in content:
                    raise kazoo.client.NoNodeError()

                content = content[path_component]

            # verified that parent exists. now delete the node.
            if last not in content:
                raise kazoo.client.NoNodeError()
            else:
                del content[last]

        def mock_get(zkpath, watch=None):
            """Traverse data recursively, return the node content."""
            path = zkpath.split('/')
            path.pop(0)
            content = zk_content
            while path:
                path_component = path.pop(0)
                if path_component not in content:
                    raise kazoo.client.NoNodeError()

                content = content[path_component]

            # Content is a copy of the zk data
            content = copy.copy(content)
            # Setup a fake metadata values
            meta_dict = {}
            if isinstance(content, dict):
                meta_values = content.pop('.metadata', {})
                meta_dict.update(meta_values)
                data = content.pop('.data', yaml.dump(content))
                # Allow override for mock testing, if not set, derive
                # children_count from num of children from the mock data.
                if 'children_count' not in meta_dict:
                    meta_dict['children_count'] = len(content)
            else:
                data = content

            # Generate the final readonly metadata
            metadata = MockZookeeperMetadata.from_dict(meta_dict)
            # Setup the watch
            watches[(zkpath, states.EventType.CHANGED)] = watch

            return (data, metadata)

        def mock_get_children(zkpath, watch=None):
            """Traverse data recursively, returns element keys."""
            path = zkpath.split('/')
            path.pop(0)

            content = zk_content
            while path:
                path_component = path.pop(0)
                content = content[path_component]

            watches[(zkpath, states.EventType.CHILD)] = watch
            if isinstance(content, dict):
                # Ignore "system" keys (.data, .metadata)
                children = [k for k in content.keys() if not k.startswith('.')]
                return sorted(children)
            else:
                return []

        if events:
            self.watch_events = queue.Queue()

            def run_events():
                """Invoke watcher callback for each event."""
                while True:
                    event = self.watch_events.get()
                    if event == 'exit':
                        break

                    delay, event_type, state, path = event
                    if delay:
                        time.sleep(delay)
                    watch = watches.get((path, event_type), None)
                    if watch:
                        watch(states.WatchedEvent(type=event_type,
                                                  state=state,
                                                  path=path))

            threading.Thread(target=run_events).start()

        side_effects = [
            (kazoo.client.KazooClient.exists, mock_exists),
            (kazoo.client.KazooClient.get, mock_get),
            (kazoo.client.KazooClient.delete, mock_delete),
            (kazoo.client.KazooClient.get_children, mock_get_children)]

        for mthd, side_effect in side_effects:
            try:
                mthd.side_effect = side_effect
            except AttributeError:
                # not mocked.
                pass

    def notify(self, event_type, path, state=states.KazooState.CONNECTED,
               delay=None):
        """Notify watchers of the event."""
        self.watch_events.put((delay, event_type, state, path))
