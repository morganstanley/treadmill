"""GSSAPI line client."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import base64
import socket

import gssapi  # pylint: disable=import-error


_LOGGER = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 10


class GSSError(Exception):
    """GSS error.
    """


class GSSAPILineClient:
    """GSSAPI line based syncrounos client."""

    def __init__(self, host, port, service_name, connect_timeout=None):
        self.host = host
        self.port = port
        self.service_name = service_name
        self.connect_timeout = connect_timeout
        if self.connect_timeout is None:
            self.connect_timeout = _CONNECT_TIMEOUT

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
        try:
            self.sock.settimeout(self.connect_timeout)
            self.sock.connect(server_address)
        except socket.error:
            _LOGGER.debug('Connection timeout: %s:%s', self.host, self.port)
            return False

        self.sock.settimeout(None)
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
