"""Start Treadmill PGE server.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import plugin_manager
from treadmill import webutils

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import pge_server

_LOGGER = logging.getLogger(__name__)


def init():
    """App main."""

    @click.command()
    @click.option('-l', '--listen',
                  help='PGE HTTP server listening address',
                  required=True, default='unix:/tmp/pge.sock')
    @click.option('-P', '--policy',
                  help='Policy file location',
                  required=False)
    @click.option('-a', '--auth', type=click.Choice(['spnego', 'trusted']))
    def pge(listen, auth=None, policy=None):
        """Create pge server to provide authorize service."""

        server = pge_server.Server(policy)

        proto, address = listen.split(':', 2)

        if proto == 'tcp':
            if auth is None:
                app = server.app
            else:
                auth = plugin_manager.load(
                    'treadmill.rest.authentication', auth)
                app = auth.wrap(server.app, ['/*'])
            webutils.run_wsgi(app, int(address))
        elif proto == 'unix':
            webutils.run_wsgi_unix(server.app, address)
        else:
            raise ValueError('Unknown proto %s' % proto)

    return pge
