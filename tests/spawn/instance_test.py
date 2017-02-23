"""
Unit test for treadmill.spawn.instance.
"""

import time
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

import treadmill
from treadmill.spawn import instance


class InstanceTest(unittest.TestCase):
    """Tests for teadmill.spawn.instance"""

    # Disable W0212: Access to a protected member
    # pylint: disable=W0212

    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._get_user_safe',
                mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._read_manifest_file',
                mock.Mock())
    def test_read_instance_file(self):
        """Tests reading the instance file."""
        inst = instance.Instance('/does/not/exist', './test.yml')

        mocked_open = mock.mock_open(read_data='name#1')
        with mock.patch('treadmill.spawn.instance.open',
                        mocked_open, create=True):
            inst._read_instance_file()

            self.assertEqual('name#1', inst.instance)

    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._get_user_safe',
                mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._read_instance_file',
                mock.Mock())
    def test_read_manifest_file(self):
        """Tests reading the manifest file with settings."""
        inst = instance.Instance('/does/not/exist', './test.yml')

        manifest_content = """
name: test2
stop: false
reconnect: 6000
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
            inst._read_manifest_file()

            self.assertEqual('test2', inst.settings['name'])
            self.assertEqual(False, inst.settings['stop'])
            self.assertEqual(6000, inst.settings['reconnect'])
            self.assertEqual('150M', inst.manifest['memory'])

    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._get_user_safe',
                mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._read_instance_file',
                mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._read_manifest_file',
                mock.Mock())
    def test_parse_instance(self):
        """Tests parsing the instance result."""
        inst = instance.Instance('/does/not/exist', './test.yml')

        inst._parse_instance('  proid.name#000123  ')

        self.assertEqual('proid.name#000123', inst.instance)
        self.assertEqual('000123', inst.instance_no)

    @mock.patch('time.time', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.fs.rm_safe', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._get_user_safe',
                mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._read_instance_file',
                mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._read_manifest_file',
                mock.Mock())
    @mock.patch('treadmill.spawn.instance._LOGGER', mock.Mock())
    def test_remove_manifest(self):
        """Tests removing a manifest."""
        inst = instance.Instance('/does/not/exist', './test.yml')

        inst.instance = 'test#1'
        inst.settings['reconnect'] = 0

        inst.remove_manifest()

        self.assertIsNone(inst.instance)

        inst.instance = 'test#1'
        inst.settings['reconnect'] = 600
        inst.start_time = 0
        time.time.return_value = 500

        inst.remove_manifest()

        self.assertEquals('test#1', inst.instance)

        inst.instance = 'test#1'
        inst.settings['reconnect'] = 600
        inst.start_time = 0
        time.time.return_value = 700

        inst.remove_manifest()

        self.assertIsNone(inst.instance)

        self.assertEqual(2, treadmill.subproc.check_call.call_count)

    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.fs.rm_safe', mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._get_user_safe',
                mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._read_instance_file',
                mock.Mock())
    @mock.patch('treadmill.spawn.instance.Instance._read_manifest_file',
                mock.Mock())
    @mock.patch('treadmill.api.instance.API', mock.Mock())
    def test_stop(self):
        """Tests stop logic."""
        inst = instance.Instance('/does/not/exist', './test.yml')

        inst.instance = 'test#1'

        inst.stop(0)

        self.assertIsNone(inst.instance)

        inst.instance = 'test#1'
        inst.settings['stop'] = False
        inst.stop(1)

        self.assertEquals('test#1', inst.instance)

        inst.instance = 'test#1'
        inst.settings['stop'] = True
        inst.stop(1)

        self.assertIsNone(inst.instance)

        inst.instance = 'test#1'
        inst.settings['stop'] = False
        inst.stop(11)

        self.assertIsNone(inst.instance)


if __name__ == '__main__':
    unittest.main()
