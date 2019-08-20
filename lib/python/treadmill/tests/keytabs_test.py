"""Unit test for keytabs
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import tempfile
import unittest

import mock

from treadmill import keytabs


class KeytabsTest(unittest.TestCase):
    """test keytabs function
    """

    def setUp(self):
        self.spool_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.spool_dir)

    def _touch_file(self, name):
        with io.open(os.path.join(self.spool_dir, name), 'w'):
            pass

    @mock.patch('treadmill.subproc.check_call')
    def test_add_keytabs_to_file(self, mock_check_call):
        """test add keytabs princ files into dest file
        """
        self._touch_file('HTTP#foo@realm')
        self._touch_file('HTTP#bar@realm')
        self._touch_file('host#foo@realm')
        self._touch_file('host#bar@realm')

        keytabs.add_keytabs_to_file(self.spool_dir, 'host', 'krb5.keytab')
        try:
            mock_check_call.assert_called_once_with(
                [
                    'kt_add', 'krb5.keytab',
                    os.path.join(self.spool_dir, 'host#foo@realm'),
                    os.path.join(self.spool_dir, 'host#bar@realm'),
                ]
            )
        except AssertionError:
            # then should called with files in other order
            mock_check_call.assert_called_once_with(
                [
                    'kt_add', 'krb5.keytab',
                    os.path.join(self.spool_dir, 'host#bar@realm'),
                    os.path.join(self.spool_dir, 'host#foo@realm'),
                ]
            )


if __name__ == '__main__':
    unittest.main()
