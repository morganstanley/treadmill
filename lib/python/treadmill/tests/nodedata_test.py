"""Unit test for cellconfig.
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

from treadmill import nodedata  # pylint: disable=no-name-in-module


class NodedataTest(unittest.TestCase):
    """Test class to read cell config
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self._file = os.path.join(self.root, 'node.json')
        with io.open(self._file, 'w') as f:
            f.write('{"foo": "bar"}')

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_get_data(self):
        """Test get data from cell config file
        """
        data = nodedata.get(self.root)
        self.assertEqual(data, {'foo': 'bar'})


if __name__ == '__main__':
    unittest.main()
