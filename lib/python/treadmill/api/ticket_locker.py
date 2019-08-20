"""Implementation of Ticket Locker API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import json

from treadmill import exc


_LOGGER = logging.getLogger(__name__)


class API:
    """Treadmill Ticket Locker REST api."""
    # pylint: disable=too-many-statements

    def __init__(self, info_dir=None):

        self._info_dir = info_dir

        def _list():
            """List configured instances."""
            return os.listdir(self._info_dir)

        def get(rsrc_id):
            """Get instance configuration."""
            try:
                tkt_info = os.path.join(self._info_dir, rsrc_id)
                _LOGGER.info('Processing: %s', tkt_info)
                with open(tkt_info) as f:
                    return json.loads(f.read())
            except FileNotFoundError:
                raise exc.NotFoundError(rsrc_id)

        self.list = _list
        self.get = get
