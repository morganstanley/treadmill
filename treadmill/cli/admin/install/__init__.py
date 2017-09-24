"""Implementation of treadmill-admin-install CLI plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import pkgutil
import sys

import click

import treadmill
from treadmill import cli
from treadmill import context
from treadmill import yamlwrapper as yaml


__path__ = pkgutil.extend_path(__path__, __name__)


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_commands(__name__))
    @click.option('--install-dir', required=True,
                  help='Target installation directory.',
                  envvar='TREADMILL_APPROOT')
    @click.option('--profile', required=False, help='Install profile.',
                  envvar='TREADMILL_PROFILE')
    @click.option('--cell', required=True, envvar='TREADMILL_CELL')
    @click.option('--config', required=False,
                  type=click.Path(exists=True, readable=True, allow_dash=True),
                  multiple=True)
    @click.option('--override', required=False, type=cli.DICT)
    @click.pass_context
    def install(ctx, install_dir, profile, cell, config, override):
        """Installs Treadmill."""
        if cell == '-':
            cell = None

        if cell:
            context.GLOBAL.cell = cell

        ctx.obj['PARAMS'] = {
            'cell': cell,
            'dns_domain': context.GLOBAL.dns_domain,
            'ldap_suffix': context.GLOBAL.ldap_suffix,
            'treadmill': treadmill.TREADMILL,
            'dir': install_dir,
            'profile': profile,
            'python': sys.executable,
            'python_path': os.getenv('PYTHONPATH', ''),
        }

        for conf in config:
            if conf == '-':
                ctx.obj['PARAMS'].update(yaml.load(stream=sys.stdin))
            else:
                with io.open(conf, 'r') as fd:
                    ctx.obj['PARAMS'].update(yaml.load(stream=fd))

        if override:
            ctx.obj['PARAMS'].update(override)

        # XXX: hack - templates use treadmillid, but it is defined as
        #      "username" in cell object.
        ctx.obj['PARAMS']['treadmillid'] = ctx.obj['PARAMS'].get('username')

        os.environ['TREADMILL'] = treadmill.TREADMILL

    return install
