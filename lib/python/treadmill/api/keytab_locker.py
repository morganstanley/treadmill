"""Implementation of keytab Locker API.
Now the api is only used for quering
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

_LOGGER = logging.getLogger(__name__)


class API:
    """Treadmill keytab Locker REST api."""

    def __init__(self, keytab_dir=None):

        self._keytab_dir = keytab_dir

        def _list():
            """List configured instances."""
            return os.listdir(self._keytab_dir)

        self.list = _list
