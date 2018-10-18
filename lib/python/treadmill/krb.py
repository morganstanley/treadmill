"""Handles Kerberos tickets sending to the cell ticket locker.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import socket

from treadmill import subproc

_LOGGER = logging.getLogger(__name__)


def _check(host, port):
    """Check ticket receiver's health."""
    sock = None
    active = False
    try:
        sock = socket.create_connection((host, port), 1)
        active = True
    except socket.error:
        _LOGGER.warning('Ticket endpoint is down: %s:%s', host, port)
    finally:
        if sock:
            sock.close()

    return active


def _send(cmd):
    """Actually run send tickets command."""
    success = False
    try:
        rc = subproc.call(cmd)
        if rc == 0:
            success = True
    except subproc.CalledProcessError:
        pass  # command failed

    return success


def send(host, port, purge=True, tktfwd_spn=None):
    """Run send tickets command."""
    success = False
    if _check(host, port):
        cmd = [
            'tkt_send_v2',
            '-h{}'.format(host),
            '-p{}'.format(port),
        ]
        if purge:
            cmd.append("--purge")
        if tktfwd_spn:
            cmd.append('--service={}'.format(tktfwd_spn))

        success = _send(cmd)

    return success


def forward(cell, hostports, tktfwd_spn=None):
    """Forward tickets to several ticket lockers."""
    failure = 0

    for idx, hostport in enumerate(hostports):
        host, port = hostport
        _LOGGER.info(
            'Forwarding tickets to cell: %s/%d - %s:%s',
            cell,
            idx,
            host,
            port
        )
        # purge from windows client?
        purge = bool(os.name == 'nt' and idx == 0)
        if not send(host, port, purge=purge, tktfwd_spn=tktfwd_spn):
            failure += 1

    return failure
