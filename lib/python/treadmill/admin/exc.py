"""Admin exception module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


class NoSuchObjectResult(Exception):
    """Admin backend exception raised if object is not found."""
    pass


class AlreadyExistsResult(Exception):
    """Admin backend exception raised when object already exists."""
    pass
