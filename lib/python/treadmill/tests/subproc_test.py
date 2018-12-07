"""Tests subproc.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import functools
import unittest

import mock

from treadmill import subproc


class SubprocTest(unittest.TestCase):
    """Tests for teadmill.subproc
    """

    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={
        'foo': 'bar',
        'xxx': functools.partial(os.path.join, '/x/y/z'),
        'xxx_d': functools.partial(os.path.join, '/x/y/z')('.'),
    }))
    @mock.patch('treadmill.subproc._check', mock.Mock(return_value=True))
    def test_resolve(self):
        """Test resolve.
        """
        self.assertEqual(subproc.resolve('foo'), 'bar')
        if os.name == 'nt':
            self.assertEqual(subproc.resolve('xxx'), '\\x\\y\\z\\xxx')
            self.assertEqual(subproc.resolve('xxx_d'), '\\x\\y\\z')
        else:
            self.assertEqual(subproc.resolve('xxx'), '/x/y/z/xxx')
            self.assertEqual(subproc.resolve('xxx_d'), '/x/y/z')
