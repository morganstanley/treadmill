"""Warpgate policy server.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import json
import logging

from . import lineserver


_LOGGER = logging.getLogger(__name__)


class GSSAPIJsonServer(lineserver.GSSAPILineServer):
    """JSON gssapi server."""

    @abc.abstractmethod
    def on_request(self, request):
        """Invoked with request deserialized from json.

        :param ``request`` dict:
            Data received from the client.
        """

    def got_line(self, data):
        """Line callback.
        """
        try:
            request = json.loads(data.decode())
            _LOGGER.info('Got client request: %s - %r', self.peer(), request)

            reply = self.on_request(request)
            self.write(json.dumps(reply).encode())
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception('Unhandled error: %r', err)
            reply = {
                '_error': str(err)
            }
            self.write(json.dumps(reply).encode())
            self.transport.loseConnection()
