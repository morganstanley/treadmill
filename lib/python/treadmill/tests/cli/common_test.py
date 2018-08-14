"""Unit tests for cli common utils
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from treadmill import cli


class CommonTest(unittest.TestCase):
    """Tests for cli common utils"""

    def test_cli_dict(self):
        """Test cli.DICT"""
        self.assertEqual(
            cli.DICT.convert(
                'test1=1,test2=2', None, None
            ),
            {
                'test1': '1',
                'test2': '2'
            }
        )
        self.assertEqual(
            cli.DICT.convert(
                'proid1.stateapi.test=1,proid2.app-dns.test=2', None, None
            ),
            {
                'proid1.stateapi.test': '1',
                'proid2.app-dns.test': '2'
            }
        )


if __name__ == '__main__':
    unittest.main()
