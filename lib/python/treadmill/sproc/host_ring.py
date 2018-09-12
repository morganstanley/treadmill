"""Treadmill host-ring service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import logging
import os
import sys
import tempfile

import click

from treadmill import cli
from treadmill import context
from treadmill.websocket import client as ws_client


_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""

    ctx = {}

    @click.group(name='host-ring')
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--aliases-dir', required=True,
                  help='Host aliases dir.',
                  default='/run/host-aliases')
    def host_ring(aliases_dir):
        """Manage /etc/hosts file inside the container."""
        ctx['aliases_dir'] = aliases_dir

    @host_ring.command(name='identity-group')
    @click.option('--pattern', required=False,
                  default='{identity_group}.{identity}')
    @click.argument('identity-group')
    def identity_group_cmd(pattern, identity_group):
        """Manage /etc/hosts file inside the container.
        """
        alias_dir = ctx['aliases_dir']
        cell = context.GLOBAL.cell

        def on_message(result):
            """Callback to process trace essage."""
            host = result.get('host')
            app = result.get('app')
            identity_group = result['identity-group']
            identity = result['identity']

            _LOGGER.info('group: %s, identity: %s, host: %s, app: %s',
                         identity_group, identity, host, app)

            alias_name = pattern.format(identity_group=identity_group,
                                        identity=identity,
                                        cell=cell)
            link_name = os.path.join(alias_dir, alias_name)
            if host:
                temp_name = tempfile.mktemp(dir=alias_dir, prefix='^')
                _LOGGER.info('Creating tempname: %s - %s', temp_name, host)
                os.symlink(host, temp_name)
                _LOGGER.info('Renaming: %s', link_name)
                os.rename(temp_name, link_name)
            else:
                os.unlink(link_name)

            return True

        def on_error(result):
            """Callback to process errors."""
            click.echo('Error: %s' % result['_error'], err=True)

        glob_pattern = os.path.join(
            alias_dir,
            pattern.format(identity_group=identity_group,
                           identity='*',
                           cell=cell)
        )

        for path in glob.glob(glob_pattern):
            os.unlink(path)

        try:
            return ws_client.ws_loop(
                context.GLOBAL.ws_api(),
                {'topic': '/identity-groups',
                 'identity-group': identity_group},
                False,
                on_message,
                on_error
            )
        except ws_client.WSConnectionError:
            click.echo('Could not connect to any Websocket APIs', err=True)
            sys.exit(-1)

    del identity_group_cmd
    return host_ring
