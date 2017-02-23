"""Treadmill spawn utilities."""
from __future__ import absolute_import

import logging
import socket

from treadmill import subproc

_LOGGER = logging.getLogger(__name__)


def open_socket(name):
    """Opens the socket and connected to the UDS."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    try:
        sock.connect('\0' + '/tms/' + name)
        return sock
    except socket.error as ex:
        _LOGGER.error(ex)
        return None


def exec_fstrace(path):
    """exec's fstrace."""
    _LOGGER.debug('watch path %r', path)
    subproc.safe_exec(['treadmill-fstrace', path])
