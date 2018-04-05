"""s6 service directory management.
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
    """Models an s6 scan directory.
    """

    __slots__ = (
        '_crash',
        '_finish',
        '_sigterm',
        '_sighup',
        '_sigquit',
        '_sigint',
        '_sigusr1',
        '_sigusr2',
    )

    _CONTROL_DIR = '.s6-svscan'

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
    def _crash_file(self):
        return os.path.join(self._control_dir, 'crash')

    @property
    def _finish_file(self):
        return os.path.join(self._control_dir, 'finish')

    @property
    def _sigterm_file(self):
        return os.path.join(self._control_dir, 'SIGTERM')

    @property
    def _sighup_file(self):
        return os.path.join(self._control_dir, 'SIGHUP')

    @property
    def _sigquit_file(self):
        return os.path.join(self._control_dir, 'SIGQUIT')

    @property
    def _sigint_file(self):
        return os.path.join(self._control_dir, 'SIGINT')

    @property
    def _sigusr1_file(self):
        return os.path.join(self._control_dir, 'SIGUSR1')

    @property
    def _sigusr2_file(self):
        return os.path.join(self._control_dir, 'SIGUSR2')

    def write(self):
        """write down the service definition.
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
