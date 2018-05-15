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

import yaml

from treadmill import cellconfig  # pylint: disable=no-name-in-module


class CellConfigTest(unittest.TestCase):
    """Test class to read cell config
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self._file = os.path.join(self.root, 'cell_config.yml')
        with io.open(self._file, 'w') as f:
            yaml.dump(
                {'data': {'foo': 'bar'},
                 'version': '3.x'},
                stream=f,
            )

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_get_data(self):
        """Test get data from cell config file
        """
        # pylint: disable=protected-access

        cell_config = cellconfig.CellConfig(self.root)
        self.assertEqual(cell_config.data, {'foo': 'bar'})
        self.assertEqual(cell_config.version, '3.x')
        self.assertEqual(cell_config.partitions, [])

        # new data after updating
        with io.open(self._file, 'w') as f:
            yaml.dump(
                {'data': {'hello': 'world'},
                 'version': '3.x'},
                stream=f,
            )
        # force lodaded data is older than file
        cell_config._modified = 0
        self.assertEqual(cell_config.data, {'hello': 'world'})


if __name__ == '__main__':
    unittest.main()
