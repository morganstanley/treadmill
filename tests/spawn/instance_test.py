"""
Unit test for treadmill.spawn.instance.
"""

import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

from treadmill.spawn import instance


class InstanceTest(unittest.TestCase):
    """Tests for teadmill.spawn.instance"""

    # Disable W0212: Access to a protected member
    # pylint: disable=W0212

    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.spawn.utils.get_user_safe',
                mock.Mock(return_value='treadmld'))
    def test_read_manifest_file(self):
        """Tests reading the manifest file with settings."""
        manifest_content = """
name: test2
stop: false
reconnect: true
reconnect_timeout: 6000
---
services:
- command: /bin/sleep 1m
  name: sleep1m
  restart:
    limit: 0
    interval: 60
memory: 150M
cpu: 10%
disk: 100M
"""
        mocked_open = mock.mock_open(read_data=manifest_content)
        with mock.patch('treadmill.spawn.instance.open',
                        mocked_open, create=True):
            inst = instance.Instance('./test.yml')

            self.assertEqual('treadmld.test2', inst.name)
            self.assertEqual(False, inst.settings['stop'])
            self.assertEqual(True, inst.settings['reconnect'])
            self.assertEqual(6000, inst.settings['reconnect_timeout'])
            self.assertEqual('150M', inst.manifest['memory'])


if __name__ == '__main__':
    unittest.main()
