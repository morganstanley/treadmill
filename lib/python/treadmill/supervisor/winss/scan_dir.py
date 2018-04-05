"""winss service directory management.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

from . import services
from .. import _scan_dir_base
from .. import _utils

_LOGGER = logging.getLogger(__name__)


class ScanDir(_scan_dir_base.ScanDir):
    """Models an winss scan directory.
    """

    __slots__ = (
        '_finish',
        '_sigterm',
    )

    _CONTROL_DIR = '.winss-svscan'

    _create_service = staticmethod(services.create_service)

    def __init__(self, directory):
        super(ScanDir, self).__init__(directory)
        for attrib in self.__slots__:
            setattr(self, attrib, None)

    @staticmethod
    def control_dir_name():
        """Gets the name of the svscan control directory.
        """
        return ScanDir._CONTROL_DIR

    @property
    def _finish_file(self):
        return os.path.join(self._control_dir, 'finish')

    @property
    def _sigterm_file(self):
        return os.path.join(self._control_dir, 'SIGTERM')

    def write(self):
        """Write down the service definition.
        """
        super(ScanDir, self).write()
        for attrib in self.__slots__:
            if getattr(self, attrib) is not None:
                attrib_filename = '%s_file' % attrib
                _utils.script_write(
                    getattr(self, attrib_filename),
                    getattr(self, attrib)
                )


# Define all the requirement properties
ScanDir.add_ctrlfile_props()


__all__ = (
    'ScanDir',
)
