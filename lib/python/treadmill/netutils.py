"""Network utility functions."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging

_LOGGER = logging.getLogger(__name__)

# Loopback - 127.0.0.1 IP
_LOOPBACK_IP = '0100007F'

_LOOPBACK_IP6 = '00000000000000000000000001000000'


def _listen_state(status, rem_addr):
    """Check if socket is in listen state."""
    return (
        status == '0A' and (
            rem_addr == '00000000:0000' or
            rem_addr == '00000000000000000000000000000000:0000'
        )
    )


def _is_loopback(local_ip):
    """Check if IP is loopback."""
    return local_ip == _LOOPBACK_IP or local_ip == _LOOPBACK_IP6


def _netstat(pid, fname):
    """Parse /proc/net/tcp and return list of ports in listen state."""
    result = set()
    _LOGGER.debug('Running netstat: %s', fname)
    try:
        with io.open(fname, 'r') as f:
            first = True
            for line in f:
                # Skip header line
                if first:
                    first = False
                    continue

                line = line.strip()
                _sl, local_addr, rem_addr, status, _ = line.split(' ', 4)
                local_ip, local_port_hex = local_addr.split(':')
                # Skip processes listening on loopback.
                if _is_loopback(local_ip):
                    continue

                port = int(local_port_hex, 16)
                if _listen_state(status, rem_addr):
                    _LOGGER.debug('pid: %s, listen port: %d', pid, port)
                    result.add(port)
    except OSError as err:
        _LOGGER.warning('Unable to read %s, %s', fname, str(err))
        return set()

    return result


def netstat(pid):
    """Parse /proc/net/tcp and return list of ports in listen state."""

    net_tcp = '/proc/{}/net/tcp'.format(pid)
    net_tcp6 = '/proc/{}/net/tcp6'.format(pid)

    result = set()
    result.update(_netstat(pid, net_tcp))
    result.update(_netstat(pid, net_tcp6))
    return result
