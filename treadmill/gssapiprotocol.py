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
#         print client.read()
#
#     client.disconnect()
#
"""


import logging
import base64
import socket

from twisted.internet import protocol
from twisted.protocols import basic

import kerberos


_LOGGER = logging.getLogger(__name__)


class GSSError(Exception):
    """GSS error."""
    pass


class GSSBase(object):
    """Base class for gss operations."""

    def __init__(self):
        self.ctx = None

        self.gss_wrap = kerberos.authGSSClientWrap
        self.gss_unwrap = kerberos.authGSSClientUnwrap
        self.gss_response = kerberos.authGSSClientResponse
        self.gss_init = kerberos.authGSSClientInit
        self.gss_step = kerberos.authGSSClientStep
        self.gss_clean = kerberos.authGSSClientClean
        self.gss_username = kerberos.authGSSClientUserName

    def step(self, in_token):
        """Perform GSS step and return the token to be sent to other side."""
        res = self.gss_step(self.ctx, in_token)
        return res, self.gss_response(self.ctx)

    def wrap(self, data):
        """GSS wrap data."""
        self.gss_wrap(self.ctx, base64.urlsafe_b64encode(data).strip())
        return self.gss_response(self.ctx)

    def unwrap(self, data):
        """GSS unwrap data."""
        self.gss_unwrap(self.ctx, data)
        response = self.gss_response(self.ctx)
        if response:
            return base64.urlsafe_b64decode(response)
        else:
            return ''


class GSSClient(GSSBase):
    """GSS client."""

    def __init__(self, service_name):

        super(GSSClient, self).__init__()

        self.gss_wrap = kerberos.authGSSClientWrap
        self.gss_unwrap = kerberos.authGSSClientUnwrap
        self.gss_response = kerberos.authGSSClientResponse
        self.gss_init = kerberos.authGSSClientInit
        self.gss_step = kerberos.authGSSClientStep
        self.gss_clean = kerberos.authGSSClientClean
        self.gss_username = kerberos.authGSSClientUserName

        gssflags = (
            kerberos.GSS_C_MUTUAL_FLAG |
            kerberos.GSS_C_SEQUENCE_FLAG |
            kerberos.GSS_C_INTEG_FLAG |
            kerberos.GSS_C_CONF_FLAG
        )
        _res, self.ctx = self.gss_init(service_name, gssflags=gssflags)


class GSSServer(GSSBase):
    """GSSServer class, accept and authentication connections."""

    def __init__(self):
        super(GSSServer, self).__init__()

        self.gss_wrap = kerberos.authGSSServerWrap
        self.gss_unwrap = kerberos.authGSSServerUnwrap
        self.gss_response = kerberos.authGSSServerResponse
        self.gss_init = kerberos.authGSSServerInit
        self.gss_step = kerberos.authGSSServerStep
        self.gss_clean = kerberos.authGSSServerClean
        self.gss_username = kerberos.authGSSServerUserName

        _res, self.ctx = self.gss_init('')

    def peer(self):
        """Returns authenticated peer name."""
        return self.gss_username(self.ctx)


# Pylint complains about camelCase methods which we inherit from twisted.
#
# pylint: disable=C0103
class GSSAPILineServer(basic.LineReceiver):
    """Line based GSSAPI server."""

    delimiter = '\n'

    def __init__(self):
        self.gss_server = GSSServer()
        self.authenticated = False

    def connectionMade(self):
        """Callback invoked on new connection."""
        _LOGGER.info('connection made')

    def connectionLost(self, reason=protocol.connectionDone):
        """Callback invoked on connection lost."""
        _LOGGER.info('connection lost')

    def rawDataReceived(self, data):
        """Not implemented."""
        pass

    def lineReceived(self, line):
        """Process KNC request header."""
        if not self.authenticated:
            in_token = line
            res, out_token = self.gss_server.step(in_token)
            self.sendLine(out_token)
            if res == kerberos.AUTH_GSS_COMPLETE:
                _LOGGER.info('Authenticated.')
                self.authenticated = True
        else:
            unwrapped = self.gss_server.unwrap(line.strip())
            self.got_line(unwrapped)

    def peer(self):
        """Returns authenticated peer name."""
        return self.gss_server.peer()

    def write(self, line):
        """Write line back to the client, encrytped and encoded base64."""
        wrapped = self.gss_server.wrap(line)
        self.sendLine(wrapped)

    def got_line(self, line):
        """Invoked after authentication is done, with decrypted line as arg."""
        pass


class GSSAPILineClient(object):
    """GSSAPI line based syncrounos client."""

    def __init__(self, host, port, service_name):
        self.host = host
        self.port = port
        self.service_name = service_name

        self.sock = None
        self.stream = None
        self.gss_client = None

    def disconnect(self):
        """Disconnect from server."""
        if self.stream:
            self.stream.close()
        if self.sock:
            self.sock.close()

    def _write_line(self, line):
        """Writes line to the socket."""
        self.stream.write(line + '\n')
        self.stream.flush()

    def _read_line(self):
        """Reads line from the socket."""
        try:
            return self.stream.readline().strip()
        except Exception:  # pylint: disable=W0703
            _LOGGER.warn('Exception reading line from socket.')
            return None

    def connect(self):
        """Connect and authenticate to the server."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        server_address = (self.host, self.port)
        self.sock.connect(server_address)
        self.stream = self.sock.makefile()

        self.gss_client = GSSClient(self.service_name)

        in_token = ''
        authenticated = False
        while not authenticated:
            res, out_token = self.gss_client.step(in_token)
            if res == kerberos.AUTH_GSS_COMPLETE:
                break

            self._write_line(out_token)
            in_token = self._read_line().strip()

        _LOGGER.info('Successfully authenticated.')
        return True

    def write(self, line):
        """Write encoded and encrypted line, can be used after connect."""
        wrapped = self.gss_client.wrap(line)
        self._write_line(wrapped)

    def read(self):
        """Read encoded and encrypted line."""
        line = self._read_line()
        if line:
            return self.gss_client.unwrap(line)
        else:
            return None
