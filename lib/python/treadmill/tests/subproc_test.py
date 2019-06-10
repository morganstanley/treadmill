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


class SubprocTest(unittest.TestCase):
    """Tests for teadmill.subproc
    """
    # pylint: disable=protected-access

    def setUp(self):
        subproc._EXECUTABLES = None
        subproc.resolve_argv.cache_clear()

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

    @unittest.skipUnless(os.name == 'posix', 'Linux specific tests')
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={
        'xxx': functools.partial(os.path.join, '/x/y/z'),
        'foo2': ['/bin/foo', '-a', '-b'],
        'xxx2': lambda x: ['/bin/{}'.format(x), '--some-opt'],
    }))
    @mock.patch('treadmill.subproc._check', mock.Mock(return_value=True))
    def test_resolve_argv_posix(self):
        """Test resolve (Linux).
        """
        self.assertEqual(
            subproc.resolve_argv('/some/abs/path'),
            ['/some/abs/path']
        )
        self.assertEqual(
            subproc.resolve_argv('xxx'),
            ['/x/y/z/xxx']
        )
        self.assertEqual(
            subproc.resolve_argv('foo2'),
            ['/bin/foo', '-a', '-b']
        )
        self.assertEqual(
            subproc.resolve_argv('xxx2'),
            ['/bin/xxx2', '--some-opt']
        )

    @unittest.skipUnless(os.name == 'nt', 'Windows specific tests')
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={
        'xxx': functools.partial(os.path.join, r'\\x\y\z'),
        'foo2': [r'C:\bin\foo', '-a', '-b'],
        'xxx2': lambda x: [r'Z:\bin\{}'.format(x), '--some-opt'],
    }))
    @mock.patch('treadmill.subproc._check', mock.Mock(return_value=True))
    def test_resolve_argv_nt(self):
        """Test resolve (Windows)
        """
        self.assertEqual(
            subproc.resolve_argv(r'A:\some\abs\path'),
            [r'A:\some\abs\path']
        )
        self.assertEqual(
            subproc.resolve_argv('xxx'),
            [r'\\x\y\z\xxx']
        )
        self.assertEqual(
            subproc.resolve_argv('foo2'),
            [r'C:\bin\foo', '-a', '-b']
        )
        self.assertEqual(
            subproc.resolve_argv('xxx2'),
            [r'Z:\bin\xxx2', '--some-opt']
        )

    @unittest.skipIf(os.name == 'nt', 'windows not supported')
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={
        'ls': ['/bin/ls', '-al'],
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
        'ls': ['/bin/ls', '-al'],
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
        'ls': ['/bin/ls', '-al'],
        'mv': lambda x: ['/bin/{}'.format(x), '-v'],
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


if __name__ == '__main__':
    unittest.main()
