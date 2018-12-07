"""Unit test for vipfile.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import tempfile
import threading
import unittest

import six

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill import vipfile


class VipFileTest(unittest.TestCase):
    """Tests for teadmill.rulefile."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.vips_dir = os.path.join(self.root, 'vips')
        owner_dirs = os.path.join(self.root, 'owners')
        os.mkdir(owner_dirs)
        for owner in six.moves.range(0, 15):
            with io.open(os.path.join(owner_dirs, str(owner)), 'w'):
                pass
        self.vips = vipfile.VipMgr(
            cidr='10.0.0.0/8',
            path=self.vips_dir,
            owner_path=owner_dirs
        )

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_alloc(self):
        """Verifies that vips are allocated atomically with no duplicates."""
        vips = set()

        def alloc_thread(idx):
            """Allocate container ip."""
            ip0 = self.vips.alloc(str(idx))
            vips.add(ip0)

        threads = []
        for i in range(0, 15):
            threads.append(threading.Thread(target=alloc_thread, args=(i,)))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        self.assertEqual(len(threads), len(vips))

    def test_free(self):
        """Tests freeing the resource."""
        owner = '3'
        ip0 = self.vips.alloc(owner)
        self.assertTrue(os.path.exists(os.path.join(self.vips_dir, ip0)))
        self.vips.free(owner, ip0)
        self.assertFalse(os.path.exists(os.path.join(self.vips_dir, ip0)))
        # Calling free twice is noop.
        self.vips.free(owner, ip0)
        self.assertFalse(os.path.exists(os.path.join(self.vips_dir, ip0)))


if __name__ == '__main__':
    unittest.main()
