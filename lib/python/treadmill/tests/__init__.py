"""Checkout utilities."""

import unittest
import socket
import pkgutil
import logging

from treadmill import restclient


__path__ = pkgutil.extend_path(__path__, __name__)


_LOGGER = logging.getLogger(__name__)


def zkadmin(hostname, port, command):
    """Netcat."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((hostname, port))
    sock.sendall(command)
    sock.shutdown(socket.SHUT_WR)
    data = []
    while True:
        chunk = sock.recv(1024)
        if not chunk:
            break
        data.append(chunk)
    sock.close()
    return ''.join(data)


def connect(host, port):
    """Check host/port is up."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)

    try:
        sock.connect((host, int(port)))
        sock.close()
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


def url_check(url):
    """Check url."""
    if url.startswith('http://'):
        return _http_check(url)
    elif url.startswith('ws://'):
        # TBD
        return True


def add_test(cls, func, message, *args, **kwargs):
    """Set function as test function."""
    setattr(cls, 'test %s' % message.format(*args, **kwargs), func)
