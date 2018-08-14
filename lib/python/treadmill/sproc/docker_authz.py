"""Docker authz Sproc

Docker authz plugin implemention
REF: https://docs.docker.com/engine/extend/plugins_authorization
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import docker_authz
from treadmill import webutils

_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--user', required=True,
                  help='userid allowed to run docker container')
    @click.option('--socket', required=False,
                  default='/run/docker/plugins/authz.sock',
                  help='Path of authz plugin unix socket')
    def run(user, socket):
        """Configure local manifest and schedule app to run."""
        # client do not timeout
        _LOGGER.info('authz server listening on %s, check id %s', socket, user)
        server = docker_authz.Server(user)
        webutils.run_wsgi_unix(server.app, socket)

    return run
