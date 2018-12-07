"""Admin exception module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


class AdminBackendError(Exception):
    """Generic admin backend exception"""
    pass


class AdminConnectionError(AdminBackendError):
    """Admin backend connection error."""
    pass


class AdminAuthorizationError(AdminBackendError):
    """Admin backend authorization error."""
    pass


class NoSuchObjectResult(AdminBackendError):
    """Admin backend exception raised if object is not found."""
    pass


class AlreadyExistsResult(AdminBackendError):
    """Admin backend exception raised when object already exists."""
    pass
