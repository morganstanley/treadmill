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


def netstat(pid):
    """Parse /proc/net/tcp and return list of ports in listen state."""
    result = set()
    net_tcp = '/proc/{}/net/tcp'.format(pid)
    _LOGGER.debug('Running netstat: %s', net_tcp)
    try:
        with io.open(net_tcp, 'r') as f:
            first = True
            for line in f:
                # Skip header line
                if first:
                    first = False
                    continue

                line = line.strip()
                _sl, local_addr, rem_addr, status, _ = line.split(' ', 4)
                local_ip, local_port_hex = local_addr.split(':')
                # Skip processes listening on 127.0.0.1
                if local_ip == _LOOPBACK_IP:
                    continue
                port = int(local_port_hex, 16)
                if status == '0A' and rem_addr == '00000000:0000':
                    _LOGGER.debug('pid: %s, listen port: %d', pid, port)
                    result.add(port)
    except OSError as err:
        _LOGGER.warning('Unable to read %s, %s', net_tcp, str(err))
        return set()

    return result
