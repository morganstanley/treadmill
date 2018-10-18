"""Unit test for treadmill.appcfg
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import tempfile
import unittest

from treadmill import appcfg
from treadmill import fs


class AppCfgTest(unittest.TestCase):
    """Tests for teadmill.appcfg"""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @staticmethod
    def _write_app_yaml(event, manifest_str):
        """Helper method to create app.yaml file in the event directory.
        """
        fs.write_safe(
            event,
            lambda f: f.write(manifest_str),
            mode='w',
        )

    def test_gen_uniqueid(self):
        """Test generation of app uniqueid.
        """
        manifest = """
---
foo: bar
"""
        event_filename0 = os.path.join(self.root, 'proid.myapp#0')
        self._write_app_yaml(event_filename0, manifest)
        uniqueid1 = appcfg.gen_uniqueid(event_filename0)
        self._write_app_yaml(event_filename0, manifest)
        uniqueid2 = appcfg.gen_uniqueid(event_filename0)

        self.assertTrue(len(uniqueid1) <= 13)
        self.assertNotEqual(uniqueid1, uniqueid2)

    def test_app_unique_id(self):
        """Test returning the unique id from app unique name.
        """
        self.assertEqual(
            appcfg.app_unique_id('proid.myapp-0-00000000AAAAA'),
            '00000000AAAAA'
        )


if __name__ == '__main__':
    unittest.main()
