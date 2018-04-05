"""Zookeeper admin interface.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import socket
import logging

_LOGGER = logging.getLogger(__name__)


def netcat(hostname, port, command):
    """Send 4letter netcat to Zookeeper control port.
    """
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
    return b''.join(data).decode()


# pylint does not like "ok" as a function name.
# pylint: disable=C0103
def ok(hostname, port):
    """Send ruok command to Zookeeper instance.
    """
    try:
        return netcat(hostname, port, b'ruok\n') == 'imok'
    except socket.error:
        return False


def stat(hostname, port):
    """Send stat command to Zookeeper instance.
    """
    return netcat(hostname, port, b'stat\n')
