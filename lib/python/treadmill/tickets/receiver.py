"""Ticket locker server."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import hashlib
import io
import logging
import os

from twisted.internet import reactor
from twisted.internet import protocol

from treadmill import gssapiprotocol

_LOGGER = logging.getLogger(__name__)


# Disable warning for too many branches.
# pylint: disable=R0912
def run_server(port, tktdir):
    """Runs tickets server."""
    _LOGGER.info('Tickets receiver server starting.')

    # no __init__ method.
    #
    # pylint: disable=W0232
    class TicketReceiverServer(gssapiprotocol.GSSAPILineServer):
        """Ticket receiver server."""

        # @utils.exit_on_unhandled
        def got_line(self, data):
            """Invoked after authentication is done, decrypted data as arg.

            :param ``bytes`` data:
                Data received from the client.
            """
            _LOGGER.info('Accepted connection from %s', self.peer())
            tkt = data
            tkt_file = os.path.join(tktdir, self.peer())
            _LOGGER.info('Writing: %s %s',
                         tkt_file, hashlib.sha1(tkt).hexdigest())
            with io.open(tkt_file, 'wb') as f:
                f.write(tkt)

            self.write(b'success')

    class TicketReceiverServerFactory(protocol.Factory):
        """TicketReceiverServer factory."""

        def buildProtocol(self, addr):  # pylint: disable=C0103
            return TicketReceiverServer()

    reactor.listenTCP(port, TicketReceiverServerFactory())

    _LOGGER.info('Running ticket receiver on port: %s', port)
    reactor.run()
