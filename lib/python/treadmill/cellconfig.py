"""Module to load cell config
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


import io
import logging
import os

from treadmill import yamlwrapper as yaml

_LOGGER = logging.getLogger(__name__)
FILE_NAME = 'cell_config.yml'


class CellConfig:
    """Class to help read data from cell_config.yml
    """

    def __init__(self, app_root):
        self._modified = None
        self._path = os.path.join(app_root, FILE_NAME)
        self._data = {}
        self._get_latest_content()

    def _get_latest_content(self):
        """Load latest content of config file
        though it is not able to update now

        if failed to open the file, we throw exception
        """
        if self._modified is None:
            self._load_content()
            return

        # check if data updated
        statinfo = os.stat(self._path)
        if statinfo.st_mtime > self._modified:
            self._load_content()

    def _load_content(self):
        """Load cell_config.yaml file
        """
        _LOGGER.info('Trying to read %s', self._path)
        with io.open(self._path, 'r') as f:
            self._data = yaml.load(stream=f)
            statinfo = os.fstat(f.fileno())
            self._modified = statinfo.st_mtime

    @property
    def data(self):
        """Get data of the cell
        """
        self._get_latest_content()
        return self._data.get('data', {})

    @property
    def version(self):
        """Get the cell version
        """
        self._get_latest_content()
        return self._data.get('version', None)

    @property
    def partitions(self):
        """Get the cell partitions
        """
        self._get_latest_content()
        return self._data.get('partitions', [])
