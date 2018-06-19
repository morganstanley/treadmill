"""This contains the unit tests for treadmill.logcontext.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import unittest

from treadmill import logcontext as lc


class AdapterTest(unittest.TestCase):
    """Unit test for the Adapter class
    """

    def setUp(self):
        self.appname = 'proid.app#003'

    def test_init_with_extra_attr(self):
        """Test that the logger adapter can be used in the "traditional" way
        """
        log_adp = lc.Adapter(logging.getLogger(__name__), self.appname)
        self.assertEqual(log_adp.extra, [self.appname])

    def test_init_without_extra_attr(self):
        """
        Test that the logger adapter uses the thread local var
        if no 'extra' param is provided at init
        """
        log_adp = lc.Adapter(logging.getLogger(__name__))
        self.assertEqual(log_adp.extra, [])

        lc.LOCAL_.ctx.append('foo')
        self.assertEqual(log_adp.extra, ['foo'])


class ContainerAdapterTest(unittest.TestCase):
    """Unit test for the ContainerAdapter class
    """

    def setUp(self):
        self.ca = lc.ContainerAdapter(logging.getLogger(__name__))

    # We're testing private methods here
    # pylint: disable=W0212
    def test_dec_unique_name(self):
        """Test the decomposition of the app unique name.
        """
        self.assertEqual(
            self.ca._dec_unique_name('treadmld.app-dns-0000000019-z1DL'),
            ['treadmld.app-dns', '0000000019', 'z1DL'])
        self.assertEqual(
            self.ca._dec_unique_name('proid.foo#1234'),
            ['proid.foo', '1234', '_'])
        self.assertEqual(
            self.ca._dec_unique_name('proid.foo#1234/asdf'),
            ['proid.foo', '1234', 'asdf'])
        self.assertEqual(
            len(self.ca._dec_unique_name('proid.foo#1234/asdf/baz')), 3)
        self.assertEqual(
            self.ca._dec_unique_name('something'), ['something', '_', '_'])

    def test_fmt(self):
        """Test the log representation of the 'extra' attribute
        """
        self.assertEqual(
            self.ca._fmt('proid.app-name-appid-uniqid'),
            'proid.app-name#appid uniqid')


@unittest.skip('No you cannot nest them')
class LogContextTest(unittest.TestCase):
    """Unit test for the LogContext class
    """

    def test_nested_adapters(self):
        """Test whether adapters can be "nested"."""
        with lc.LogContext(logging.getLogger(__name__),
                           'proid.app#123') as outer:
            outer.info('foo')
            with lc.LogContext(outer, 'some.ting#123') as inner:
                inner.info('bar')


if __name__ == '__main__':
    unittest.main()
