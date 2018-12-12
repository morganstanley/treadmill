"""GSS API line server."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import base64
import abc

import gssapi  # pylint: disable=import-error

from twisted.protocols import basic


_LOGGER = logging.getLogger(__name__)


# Pylint complains about camelCase methods which we inherit from twisted.
#
class GSSAPILineServer(basic.LineReceiver):  # pylint: disable=C0103
    """Line based GSSAPI server."""

    from twisted.internet import protocol

    __slots__ = (
        '_ctx',
        '_authenticated',
    )

    delimiter = b'\n'

    def __init__(self):
        self._ctx = None
        self._authenticated = False

    def connectionMade(self):
        """Callback invoked on new connection."""
        _LOGGER.info('connection made')
        self._ctx = gssapi.SecurityContext(creds=None, usage='accept')

    def connectionLost(self, reason=protocol.connectionDone):
        """Callback invoked on connection lost."""
        _LOGGER.info('connection lost')
        self._ctx = None

    def lineReceived(self, line):
        """Process line from the clien."""
        if not self._authenticated:
            while not self._ctx.complete:
                in_token = base64.standard_b64decode(line)
                out_token = self._ctx.step(in_token)
                if out_token:
                    encoded = base64.standard_b64encode(out_token)
                    self.sendLine(encoded)
            self._authenticated = True
            _LOGGER.info('Authenticated: %s', self.peer())
        else:
            decoded = base64.standard_b64decode(line)
            assert isinstance(decoded, bytes), repr(decoded)

            try:
                decrypted = self._ctx.decrypt(decoded)
            except gssapi.exceptions.GeneralError as err:
                _LOGGER.error('Unable to decrypt message: %s', err)
                self.transport.abortConnection()
                return

            self.got_line(decrypted)

    def peer(self):
        """Returns authenticated peer name.
        """
        if self._ctx and self._ctx.complete:
            return str(self._ctx.initiator_name)
        else:
            return None

    def peercred_lifetime(self):
        """Returns lifetime peer credential.
        """
        if self._ctx and self._ctx.complete:
            return self._ctx.lifetime
        else:
            return 0

    def write(self, data):
        """Write line back to the client, encrytped and encoded base64.

        :param ``bytes`` data:
            Data to send to the client.
        """
        assert isinstance(data, bytes), repr(data)
        encrypted = self._ctx.encrypt(data)
        encoded = base64.standard_b64encode(encrypted)
        self.sendLine(encoded)

    @abc.abstractmethod
    def got_line(self, data):
        """Invoked after authentication is done, with decrypted data as arg.

        :param ``bytes`` data:
            Data received from the client.
        """

    def rawDataReceived(self, data):
        """Not implemented.
        """
