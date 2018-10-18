"""Admin forward Kerberos tickets to the cell ticket locker.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import sys

import click

from treadmill import cli
from treadmill import context
from treadmill import discovery
from treadmill import krb
from treadmill import exc

_LOGGER = logging.getLogger(__name__)

_ON_EXCEPTIONS = cli.handle_exceptions([
    (exc.InvalidInputError, None),
])


def _iterate(discovery_iter):
    """Iterate discovered endpoints."""
    hostports = []
    for (_, hostport) in discovery_iter:
        if not hostport:
            continue
        host, port = hostport.split(':')
        hostports.append((host, int(port)))

    return hostports


def init():
    """Return top level command handler"""

    @click.command()
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt)
    @click.option('--proid', required=True, help='Proid.')
    @click.option('--spn', default=None,
                  help='Service Principal Name used in the Kerberos protocol.')
    @click.argument('endpoint', required=False)
    @_ON_EXCEPTIONS
    def forward(endpoint, spn, proid, cell):
        """Forward Kerberos tickets to the cell ticket locker."""
        _LOGGER.setLevel(logging.INFO)
        if not endpoint:
            endpoint = '*'

        pattern = "{0}.tickets-v2".format(proid)
        discovery_iter = discovery.iterator(
            context.GLOBAL.zk.conn, pattern, endpoint, False)
        hostports = _iterate(discovery_iter)

        failure = krb.forward(cell, hostports, tktfwd_spn=spn)
        sys.exit(failure)

    return forward
