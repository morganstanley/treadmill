"""Checkout utilities.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import socket
import logging
import telnetlib
import websocket as ws_client

from treadmill import restclient


_LOGGER = logging.getLogger(__name__)

_SSH_PORT = 22

_SSH_EXPECT = b'SSH'


def connect(host, port):
    """Check host:port is up."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)

    try:
        sock.connect((host, int(port)))
        sock.close()
        return True
    except socket.error:
        return False


def telnet(host, port=_SSH_PORT, expect=_SSH_EXPECT, timeout=1):
    """Check telnet to host:port succeeds."""
    try:
        telnet_client = telnetlib.Telnet(host.encode(), port, timeout=timeout)
        telnet_client.read_until(expect, timeout=timeout)
        telnet_client.close()
        return True
    except socket.error:
        return False


def _http_check(url):
    """Check http url request is success."""
    try:
        resp = restclient.get(url, '/', retries=0)
        return resp.status_code == 200

    except restclient.MaxRequestRetriesError as err:
        _LOGGER.error('%s - %s', url, str(err))
        return False


def _ws_check(url):
    """Check ws url availability"""
    try:
        ws_connection = ws_client.create_connection(url, timeout=5)
        ws_connection.close()
        return True
    except Exception:  # pylint: disable=W0703
        return False


def url_check(url):
    """Check url."""
    if url.startswith('http://'):
        return _http_check(url)
    elif url.startswith('ws://'):
        return _ws_check(url)
    else:
        raise Exception('Invalid protocol: %s' % url)
