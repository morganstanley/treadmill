"""Treadmill resource service framework.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os


from ._base_service import (
    ResourceServiceError,
    ResourceServiceRequestError,
    ResourceServiceTimeoutError,
)

if os.name == 'nt':
    from ._windows_base_service import WindowsResourceService as \
        ResourceService
    from ._windows_base_service import WindowsBaseResourceServiceImpl as \
        BaseResourceServiceImpl
else:
    from ._linux_base_service import LinuxResourceService as ResourceService
    from ._linux_base_service import LinuxBaseResourceServiceImpl as \
        BaseResourceServiceImpl


__all__ = [
    'BaseResourceServiceImpl',
    'ResourceService',
    'ResourceServiceError',
    'ResourceServiceRequestError',
    'ResourceServiceTimeoutError',
]
