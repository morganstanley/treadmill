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

import kerberos
import six

from twisted.internet import protocol
from twisted.protocols import basic


_LOGGER = logging.getLogger(__name__)


class GSSError(Exception):
    """GSS error."""
    pass


@six.add_metaclass(abc.ABCMeta)
class GSSBase(object):
    """Base class for gss operations."""

    __slots__ = (
        'ctx',
    )

    def __init__(self):
        self.ctx = None

    def step(self, in_token):
        """Perform GSS step and return the token to be sent to other side.
        """
        if six.PY3:
            # XXX: Kerberos bindings want str, not bytes.
            in_token = in_token.decode()

        res = self._gss_step(self.ctx, in_token)

        out_token = self._gss_response(self.ctx)
        if six.PY3 and out_token is not None:
            # XXX: Kerberos bindings return str, not bytes.
            out_token = out_token.encode()

        return res, out_token

    def wrap(self, data):
        """GSS wrap data.
        """
        encoded_data = base64.standard_b64encode(data)
        if six.PY3:
            # XXX: Kerberos bindings want str, not bytes.
            encoded_data = encoded_data.decode()

        res = self._gss_wrap(
            self.ctx,
            encoded_data,
        )
        if res is None:
            return None
        wrapped = self._gss_response(self.ctx)
        if wrapped is None:
            return None

        if six.PY3:
            # XXX: Kerberos bindings return str, not bytes.
            wrapped = wrapped.encode()

        return wrapped

    def unwrap(self, wrapped):
        """GSS unwrap data.
        """
        if six.PY3:
            # XXX: Kerberos bindings want str, not bytes.
            wrapped = wrapped.decode()

        res = self._gss_unwrap(
            self.ctx,
            wrapped
        )
        if res is None:
            return None
        encoded_data = self._gss_response(self.ctx)
        if encoded_data is None:
            return None

        if six.PY3:
            # XXX: Kerberos bindings return str, not bytes.
            encoded_data = encoded_data.encode()
        data = base64.standard_b64decode(encoded_data)

        return data

    def peer(self):
        """Returns authenticated peer principal.

        :returns:
            ``str`` - Peer principal.
        """
        principal = self._gss_username(self.ctx)
        # NOTE: Kerberos bindings return str, not bytes.

        return principal

    def clean(self):
        """Cleanup GSS context.
        """
        self._gss_clean(self.ctx)
        self.ctx = None

    @staticmethod
    @abc.abstractmethod
    def _gss_wrap(ctx, data, username=None):
        pass

    @staticmethod
    @abc.abstractmethod
    def _gss_unwrap(ctx, data):
        pass

    @staticmethod
    @abc.abstractmethod
    def _gss_response(ctx):
        pass

    @staticmethod
    @abc.abstractmethod
    def _gss_init(service_name, gssflags=None):
        pass

    @staticmethod
    @abc.abstractmethod
    def _gss_step(ctx, token):
        pass

    @staticmethod
    @abc.abstractmethod
    def _gss_clean(ctx):
        pass

    @staticmethod
    @abc.abstractmethod
    def _gss_username(ctx):
        pass


class GSSClient(GSSBase):
    """GSS client.
    """

    __slots__ = (
    )

    def __init__(self, service_name):

        super(GSSClient, self).__init__()

        gssflags = (
            kerberos.GSS_C_MUTUAL_FLAG |
            kerberos.GSS_C_SEQUENCE_FLAG |
            kerberos.GSS_C_INTEG_FLAG |
            kerberos.GSS_C_CONF_FLAG
        )
        _res, self.ctx = self._gss_init(service_name, gssflags=gssflags)

    _gss_wrap = getattr(kerberos, 'authGSSClientWrap', None)
    _gss_unwrap = getattr(kerberos, 'authGSSClientUnwrap', None)
    _gss_response = getattr(kerberos, 'authGSSClientResponse', None)
    _gss_init = getattr(kerberos, 'authGSSClientInit', None)
    _gss_step = getattr(kerberos, 'authGSSClientStep', None)
    _gss_clean = getattr(kerberos, 'authGSSClientClean', None)
    _gss_username = getattr(kerberos, 'authGSSClientUserName', None)


class GSSServer(GSSBase):
    """GSSServer class, accept and authentication connections."""

    __slots__ = (
    )

    def __init__(self):
        super(GSSServer, self).__init__()

        _res, self.ctx = self._gss_init('')

    _gss_wrap = getattr(kerberos, 'authGSSServerWrap', None)
    _gss_unwrap = getattr(kerberos, 'authGSSServerUnwrap', None)
    _gss_response = getattr(kerberos, 'authGSSServerResponse', None)
    _gss_init = getattr(kerberos, 'authGSSServerInit', None)
    _gss_step = getattr(kerberos, 'authGSSServerStep', None)
    _gss_clean = getattr(kerberos, 'authGSSServerClean', None)
    _gss_username = getattr(kerberos, 'authGSSServerUserName', None)


# Pylint complains about camelCase methods which we inherit from twisted.
#
class GSSAPILineServer(basic.LineReceiver):  # pylint: disable=C0103
    """Line based GSSAPI server."""

    delimiter = b'\n'

    def __init__(self):
        self.gss_server = GSSServer()
        self.authenticated = False

    def connectionMade(self):
        """Callback invoked on new connection."""
        _LOGGER.info('connection made')

    def connectionLost(self, reason=protocol.connectionDone):
        """Callback invoked on connection lost."""
        _LOGGER.info('connection lost')
        self.gss_server.clean()

    def lineReceived(self, line):
        """Process KNC request header."""
        if not self.authenticated:
            res, out_token = self.gss_server.step(line)
            self.sendLine(out_token)
            if res == kerberos.AUTH_GSS_COMPLETE:
                _LOGGER.info('Authenticated.')
                self.authenticated = True
        else:
            unwrapped = self.gss_server.unwrap(line)
            assert isinstance(unwrapped, bytes), repr(unwrapped)
            self.got_line(unwrapped)

    def peer(self):
        """Returns authenticated peer name.
        """
        return self.gss_server.peer()

    def write(self, data):
        """Write line back to the client, encrytped and encoded base64.

        :param ``bytes`` data:
            Data to send to the client.
        """
        assert isinstance(data, bytes), repr(data)
        wrapped = self.gss_server.wrap(data)
        self.sendLine(wrapped)

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
        self.gss_client.clean()

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

        self.gss_client = GSSClient(self.service_name)

        in_token = b''
        authenticated = False
        while not authenticated:
            res, out_token = self.gss_client.step(in_token)
            if res == kerberos.AUTH_GSS_COMPLETE:
                break

            self._write_line(out_token)
            in_token = self._read_line()

        _LOGGER.info('Successfully authenticated.')
        return True

    def write(self, data):
        """Write encoded and encrypted line, can be used after connect.

        :param ``bytes`` data:
            Data to send to the server.
        """
        assert isinstance(data, bytes)
        wrapped = self.gss_client.wrap(data)
        self._write_line(wrapped)

    def read(self):
        """Read encoded and encrypted line.

        :returns:
            ``bytes`` - Data received from the server.
        """
        data = self._read_line()
        if not data:
            return None

        byte_line = self.gss_client.unwrap(data)
        return byte_line
