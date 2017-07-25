"""s6 service directory management.
"""

from __future__ import absolute_import

import errno
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
    )

    _CONTROL_DIR = '.s6-svscan'

    def __init__(self, directory):
        self._crash = None
        super(ScanDir, self).__init__(directory, ScanDir._CONTROL_DIR,
                                      services.create_service)

    @property
    def _crash_file(self):
        return os.path.join(self._control_dir, 'crash')

    @property
    def crash(self):
        """Get the contents of the crash file.
        """
        if self._crash is None:
            try:
                self._crash = _utils.script_read(self._crash_file)
            except IOError as err:
                if err.errno is not errno.ENOENT:
                    raise
        return self._crash

    @crash.setter
    def crash(self, new_script):
        self._crash = new_script

    def write(self):
        """Write down the service definition.
        """
        if self._crash is not None:
            _utils.script_write(self._crash_file, self._crash)
        super(ScanDir, self).write()


__all__ = (
    'ScanDir',
)
