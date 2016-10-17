"""This contains the unit tests for treadmill.logcontext."""

import logging
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611


from treadmill import logcontext


class ContainerAdapterTest(unittest.TestCase):
    """Unit test for the ContainerAdapter class
    """

    def setUp(self):
        self.ca = logcontext.ContainerAdapter(logging.getLogger(__name__))

    # We're testing private methods here
    # pylint: disable=W0212
    def test_dec_unique_name(self):
        """Test the decomposition of the app unique name.
        """
        self.assertEqual(
            self.ca._dec_unique_name('treadmld.app-dns-0000000019-z1DL'),
            ['treadmld.app-dns', '0000000019', 'z1DL'])
        self.assertEqual(
            self.ca._dec_unique_name('not a full unique name'),
            ['_', '_', '_'])

    def test_fmt(self):
        """Test the log representation of the 'extra' attribute
        """
        self.assertEqual(
            self.ca._fmt('proid.app-name-appid-uniqid'),
            'proid.app-name#appid uniqid')


if __name__ == '__main__':
    unittest.main()
