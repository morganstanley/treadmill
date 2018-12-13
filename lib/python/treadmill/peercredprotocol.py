"""UDS peercred linebased client/server protocol.
#
# Usage:
#
# Server:
#
#     class Echo(peercredprotocol.PeerCredLineServer):
#         def got_line(self, line):
#             self.write('echo: ' + line)
#
#     class EchoFactory(protocol.Factory):
#         def buildProtocol(self, addr):  # pylint: disable=C0103
#             return Echo()
#
#     def main():
#         reactor.listenUNIX('/var/run/my.sock', EchoFactory())
#         reactor.run()
#
# Client:
#
#     client = peercredprotocol.PeerCredLineClient(path)
#     if client.connect():
#
#         client.write(b'Hi')
#         print(client.read().decode())
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
import struct

from twisted.internet import protocol
from twisted.protocols import basic

from treadmill import utils

_LOGGER = logging.getLogger(__name__)


# Pylint complains about camelCase methods which we inherit from twisted.
class PeerCredLineServer(basic.LineReceiver):  # pylint: disable=C0103
    """Line based GSSAPI server."""

    delimiter = b'\n'

    def __init__(self):
        self.uid = None
        self.gid = None
        self.username = None

    def connectionMade(self):
        """Callback invoked on new connection."""
        _LOGGER.info('connection made')

    def connectionLost(self, reason=protocol.connectionDone):
        """Callback invoked on connection lost."""
        _LOGGER.info('connection lost')

    def lineReceived(self, line):
        """Process line from the clien."""
        creds = self.transport.socket.getsockopt(
            socket.SOL_SOCKET,
            socket.SO_PEERCRED,
            struct.calcsize('3i')
        )

        pid, uid, gid = struct.unpack('3i', creds)
        _LOGGER.info('Connection from pid: %d, uid: %d, gid %d', pid, uid, gid)

        try:
            self.username = utils.get_username(uid)
            self.uid = uid
            self.gid = gid

            decoded = base64.standard_b64decode(line)
            assert isinstance(decoded, bytes), repr(decoded)
            self.got_line(decoded)
        except KeyError:
            _LOGGER.warning('Unable to get username for uid: %d', uid)
            self.username = None
            self.transport.loseConnection()

    def peer(self):
        """Returns authenticated peer name.
        """
        return self.username

    def write(self, data):
        """Write line back to the client, encrytped and encoded base64.

        :param ``bytes`` data:
            Data to send to the client.
        """
        assert isinstance(data, bytes), repr(data)
        encoded = base64.standard_b64encode(data)
        self.sendLine(encoded)

    @abc.abstractmethod
    def got_line(self, data):
        """Invoked after authentication is done, with decrypted data as arg.

        :param ``bytes`` data:
            Data received from the client.
        """

    def rawDataReceived(self, data):
        """Not implemented."""


class PeerCredLineClient:
    """PeerCred line based syncrounos client."""

    def __init__(self, path):
        self.path = path
        self.sock = None
        self.stream = None

    def disconnect(self):
        """Disconnect from server."""
        if self.stream:
            self.stream.close()
        if self.sock:
            self.sock.close()

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
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.path)
        self.stream = self.sock.makefile(mode='rwb')

        _LOGGER.debug('Successfully connected.')
        return True

    def write(self, data):
        """Write encoded and encrypted line, can be used after connect.

        :param ``bytes`` data:
            Data to send to the server.
        """
        assert isinstance(data, bytes)
        encoded = base64.standard_b64encode(data)
        self._write_line(encoded)

    def read(self):
        """Read encoded and encrypted line.

        :returns:
            ``bytes`` - Data received from the server.
        """
        data = self._read_line()
        if not data:
            return None

        decoded = base64.standard_b64decode(data)
        assert isinstance(decoded, bytes), repr(decoded)
        return decoded
