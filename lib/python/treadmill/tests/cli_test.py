"""Unit test for treadmill.cli.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import sys
import unittest

import click
import mock

import six

from treadmill import cli
from treadmill import context
from treadmill.formatter import tablefmt


def _lines(tbl):
    """Convert table to list of lines."""
    return list(six.moves.map(str.strip, str(tbl).splitlines()))


class CliTest(unittest.TestCase):
    """These are Tests for teadmill.warm."""

    def test_table(self):
        """Tests table output."""
        schema = [('A', 'a', None),
                  ('b', None, None),
                  ('c', None, None)]

        tbl = tablefmt.make_dict_to_table(schema)
        list_tbl = tablefmt.make_list_to_table(schema)

        self.assertEqual(
            _lines(tbl({'a': 1, 'b': 2, 'c': [1, 2, 3]})),
            ['A  :  1',
             'b  :  2',
             'c  :  1,2,3']
        )

        self.assertEqual(
            _lines(list_tbl([{'a': 1, 'b': 2, 'c': [1, 2, 3]}])),
            ['A  b  c',
             '1  2  1,2,3']
        )

    @mock.patch('click.echo', mock.Mock())
    @mock.patch('sys.exit', mock.Mock())
    def test_exceptions_wrapper(self):
        """Tests wrapping function with exceptions wrapper."""
        class AExc(Exception):
            """Sample exception.
            """

        class BExc(Exception):
            """Another exception.
            """

        on_exceptions = cli.handle_exceptions([
            (AExc, 'a'),
            (BExc, 'b'),
        ])

        @on_exceptions
        def _raise_a():
            """Raise A exception."""
            raise AExc()

        @on_exceptions
        def _raise_b():
            """Raise B exception."""
            raise BExc()

        _raise_a()
        click.echo.assert_called_with('a', err=True)
        sys.exit.assert_called_with(1)
        click.echo.reset_mock()
        sys.exit.reset_mock()

        _raise_b()
        click.echo.assert_called_with('b', err=True)
        sys.exit.assert_called_with(1)

    def test_combine(self):
        """Test combining lists.
        """
        self.assertEqual(['a', 'b', 'c'], cli.combine(['a', 'b,c']))
        self.assertEqual(None, cli.combine(['-']))

    def test_handle_cell_opt(self):
        """Test parsing cell CLI option."""
        param = collections.namedtuple('param', 'name')('cell')
        ctx = collections.namedtuple('ctx', 'resilient_parsing')(False)
        cli.handle_context_opt(ctx, param, 'foo')
        self.assertEqual(context.GLOBAL.cell, 'foo')

    def test_handle_fq_cell_opt(self):
        """Test parsing cell CLI option."""
        param = collections.namedtuple('param', 'name')('cell')
        ctx = collections.namedtuple('ctx', 'resilient_parsing')(False)
        cli.handle_context_opt(ctx, param, 'foo.xx.com')
        self.assertEqual(context.GLOBAL.cell, 'foo')
        self.assertEqual(context.GLOBAL.dns_domain, 'xx.com')


if __name__ == '__main__':
    unittest.main()
