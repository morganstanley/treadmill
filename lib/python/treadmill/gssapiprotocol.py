"""GSSAPI linebased client/server protocol.
#
# Usage:
#
# Server:
#
#     class Echo(gssapiprotocol.GSSAPILineServer):
#         def got_line(self, line):
#             self.write('echo: ' + line)
#
#     class EchoFactory(protocol.Factory):
#         def buildProtocol(self, addr):  # pylint: disable=C0103
#             return Echo()
#
#     def main():
#         reactor.listenTCP(8080, EchoFactory())
#         reactor.run()
#
# Client:
#
#     client = gssapiprotocol.GSSAPILineClient(host, port, service)
#     if client.connect():
#
#         client.write('Hi')
#         print(client.read())
#
#     client.disconnect()
#
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import base64
import abc
import socket

import gssapi

from twisted.internet import protocol
from twisted.protocols import basic


_LOGGER = logging.getLogger(__name__)


class GSSError(Exception):
    """GSS error."""
    pass


# Pylint complains about camelCase methods which we inherit from twisted.
#
class GSSAPILineServer(basic.LineReceiver):  # pylint: disable=C0103
    """Line based GSSAPI server."""

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
        pass

    def rawDataReceived(self, data):
        """Not implemented."""
        pass


class GSSAPILineClient:
    """GSSAPI line based syncrounos client."""

    def __init__(self, host, port, service_name):
        self.host = host
        self.port = port
        self.service_name = service_name

        self.sock = None
        self.stream = None
        self.ctx = None

    def disconnect(self):
        """Disconnect from server."""
        if self.stream:
            self.stream.close()
        if self.sock:
            self.sock.close()
        self.ctx = None

    def _write_line(self, line):
        """Writes line to the socket."""
        self.stream.write(line + b'\n')
        self.stream.flush()

    def _read_line(self):
        """Reads line from the socket."""
        try:
            return self.stream.readline()[:-1]
        except Exception:  # pylint: disable=W0703
            _LOGGER.warning('Exception reading line from socket.')
            return None

    def connect(self):
        """Connect and authenticate to the server."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        server_address = (self.host, self.port)
        self.sock.connect(server_address)
        self.stream = self.sock.makefile(mode='rwb')

        service_name = gssapi.Name(
            self.service_name,
            name_type=gssapi.NameType.hostbased_service
        )
        self.ctx = gssapi.SecurityContext(name=service_name, usage='initiate')

        in_token = None
        while not self.ctx.complete:
            out_token = self.ctx.step(in_token)
            if out_token:
                out_encoded = base64.standard_b64encode(out_token)
                self._write_line(out_encoded)
            if self.ctx.complete:
                break
            in_encoded = self._read_line()
            in_token = base64.standard_b64decode(in_encoded)

            if not in_token:
                raise GSSError('No response from server.')

        _LOGGER.debug('Successfully authenticated.')
        return True

    def write(self, data):
        """Write encoded and encrypted line, can be used after connect.

        :param ``bytes`` data:
            Data to send to the server.
        """
        assert isinstance(data, bytes)
        encrypted = self.ctx.encrypt(data)
        encoded = base64.standard_b64encode(encrypted)
        self._write_line(encoded)

    def read(self):
        """Read encoded and encrypted line.

        :returns:
            ``bytes`` - Data received from the server.
        """
        data = self._read_line()
        if not data:
            return None

        # byte_line = self.gss_client.unwrap(data)
        decoded = base64.standard_b64decode(data)
        assert isinstance(decoded, bytes), repr(decoded)
        return self.ctx.decrypt(decoded)
