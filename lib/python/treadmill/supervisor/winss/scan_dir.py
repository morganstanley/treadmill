"""winss service directory management.
"""


from __future__ import absolute_import

import logging

from . import services
from .. import _scan_dir_base

_LOGGER = logging.getLogger(__name__)


class ScanDir(_scan_dir_base.ScanDir):
    """Models an winss scan directory.
    """

    __slots__ = (
    )

    _CONTROL_DIR = '.winss-svscan'

    def __init__(self, directory):
        super(ScanDir, self).__init__(directory, ScanDir._CONTROL_DIR,
                                      services.create_service)


__all__ = (
    'ScanDir',
)
