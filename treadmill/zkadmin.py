"""Zookeeper admin interface."""

import socket
import logging


_LOGGER = logging.getLogger(__name__)


def netcat(hostname, port, command):
    """Send 4letter netcat to Zookeeper control port."""
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
