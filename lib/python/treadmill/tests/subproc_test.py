"""Tests subproc.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import functools
import unittest
import subprocess

import mock

from treadmill import subproc


# pylint: disable=protected-access
class SubprocTest(unittest.TestCase):
    """Tests for teadmill.subproc
    """

    def setUp(self):
        subproc._EXECUTABLES = None
        subproc.resolve.cache_clear()

    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={
        'foo': 'bar',
        'xxx': functools.partial(os.path.join, '/x/y/z'),
        'xxx_d': functools.partial(os.path.join, '/x/y/z')('.'),
        'lib': '/x/$LIB/lib.so',
    }))
    @mock.patch('treadmill.subproc._check', mock.Mock(return_value=True))
    def test_resolve(self):
        """Test resolve.
        """
        self.assertEqual(subproc.resolve('foo'), 'bar')

        if os.name != 'nt':
            self.assertEqual(subproc.resolve('lib'), '/x/$LIB/lib.so')

        if os.name == 'nt':
            self.assertEqual(subproc.resolve('xxx'), '\\x\\y\\z\\xxx')
            self.assertEqual(subproc.resolve('xxx_d'), '\\x\\y\\z')
        else:
            self.assertEqual(subproc.resolve('xxx'), '/x/y/z/xxx')
            self.assertEqual(subproc.resolve('xxx_d'), '/x/y/z')

    @unittest.skipIf(os.name == 'nt', 'windows not supported')
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={
        'ls': '/bin/ls -al',
        'mv': functools.partial(os.path.join, '/bin', '.'),
    }))
    @mock.patch('treadmill.subproc._check', mock.Mock(return_value=True))
    def test_resolve_shlex(self):
        """Test resolve.
        """
        self.assertEqual(subproc.resolve('ls'), '/bin/ls -al')
        self.assertEqual(subproc.resolve('mv'), '/bin/mv')

    @unittest.skipIf(os.name == 'nt', 'windows not supported')
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={
        'ls': '/bin/ls -al',
    }))
    @mock.patch('subprocess.call', mock.Mock())
    def test_command(self):
        """Test command invocation.
        """
        subproc.call(['ls', '/tmp'])
        subprocess.call.assert_called_with(
            ['/bin/ls', '-al', '/tmp'], env=mock.ANY, close_fds=True
        )

    @unittest.skipIf(os.name == 'nt', 'windows not supported')
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={
        'ls': '/bin/ls -al',
        'mv': functools.partial('/bin/{} -v'.format),
    }))
    def test_alias_cmd(self):
        """Test resolving alias command.
        """
        self.assertEqual(
            subproc._alias_command(['ls', '/tmp']),
            ['/bin/ls', '-al', '/tmp']
        )
        self.assertEqual(
            subproc._alias_command(['mv', 'a', 'b']),
            ['/bin/mv', '-v', 'a', 'b']
        )
