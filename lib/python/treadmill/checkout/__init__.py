"""Checkout utilities."""

from __future__ import print_function

import unittest
import socket
import pkgutil
import logging
import telnetlib
import functools
import hashlib

import decorator
import websocket as ws_client

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
    """Check host:port is up."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)

    try:
        sock.connect((host, int(port)))
        sock.close()
        return True
    except socket.error:
        return False


def telnet(host, port, expect='SSH', timeout=1):
    """Check telnet to host:port succeeds."""
    print('telnet %s %s, expect: %s' % (host, port, expect))
    telnet_client = telnetlib.Telnet(host, port, timeout=timeout)
    telnet_client.read_until(expect, timeout=timeout)
    telnet_client.close()
    return True


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
    except:  # pylint: disable=W0702
        return False


def url_check(url):
    """Check url."""
    if url.startswith('http://'):
        return _http_check(url)
    elif url.startswith('ws://'):
        return _ws_check(url)


def add_test(cls, func, message, *args, **kwargs):
    """Set function as test function."""
    setattr(cls, 'test %s' % message.format(*args, **kwargs), func)


class T(object):  # pylint: disable=C0103
    """Decorator to create a new test case."""

    def __init__(self, cls, **kwargs):
        self.cls = cls
        self.kwargs = kwargs

    def __call__(self, func):

        partial = functools.partial(func, **self.kwargs)
        # Lambda is necessary as unittest refuses to work with partial
        # objects. Disable pylint warning.
        test_func = lambda me: partial(me)  # pylint: disable=W0108
        test_func.__doc__ = func.__doc__.format(**self.kwargs)
        hash_md5 = hashlib.md5()
        for name, value in self.kwargs.iteritems():
            hash_md5.update(name)
            hash_md5.update(str(value))
        setattr(
            self.cls, 'test_%s_%r_%s.' % (
                func.__name__,
                self.kwargs.keys(),
                hash_md5.hexdigest()
            ),
            test_func
        )
        return func
