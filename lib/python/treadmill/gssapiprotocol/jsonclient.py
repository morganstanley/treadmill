"""Json GSSAPI client.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging

from . import lineclient


_LOGGER = logging.getLogger(__name__)


class GSSAPIJsonClient(lineclient.GSSAPILineClient):
    """JSON gssapi client."""

    def write_json(self, request):
        """Write serialized json object."""
        return self.write(json.dumps(request).encode())

    def read_json(self):
        """Read reply, deserialize json to dict."""
        reply = self.read()
        if reply is None:
            return None
        else:
            return json.loads(reply.decode())
