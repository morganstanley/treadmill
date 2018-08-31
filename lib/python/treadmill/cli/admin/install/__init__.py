"""Implementation of treadmill-admin-install CLI plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import sys

import click

from treadmill import cli
from treadmill import context
from treadmill import yamlwrapper as yaml


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_commands(__name__))
    @click.option('--distro', required=True,
                  help='Path to treadmill distro.',
                  envvar='TREADMILL_DISTRO')
    @click.option('--install-dir', required=True,
                  help='Target installation directory.',
                  envvar='TREADMILL_APPROOT')
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  is_eager=True,
                  expose_value=True)
    @click.option('--config', required=False,
                  type=click.Path(exists=True, readable=True, allow_dash=True),
                  multiple=True)
    @click.option('--override', required=False, type=cli.DICT)
    @click.option('--profile', required=True,
                  envvar='TREADMILL_PROFILE',
                  callback=cli.handle_context_opt,
                  is_eager=True,
                  expose_value=False)
    @click.pass_context
    def install(ctx, cell, distro, install_dir, config, override):
        """Installs Treadmill."""

        profile = context.GLOBAL.get_profile_name()

        ctx.obj['PARAMS'] = {
            'dns_domain': context.GLOBAL.dns_domain,
            'ldap_suffix': context.GLOBAL.ldap_suffix,
            'treadmill': distro,
            'dir': install_dir,
            'profile': profile,
            'python': sys.executable,
            'python_path': os.getenv('PYTHONPATH', ''),
        }
        if cell is not None:
            ctx.obj['PARAMS']['cell'] = context.GLOBAL.cell

        install_data = {}

        for conf in config:
            if conf == '-':
                conf_dict = yaml.load(stream=sys.stdin)
            else:
                with io.open(conf, 'r') as fd:
                    conf_dict = yaml.load(stream=fd)

            ctx.obj['PARAMS'].update(conf_dict)
            install_data.update(conf_dict.get('data', {}))

        if override:
            ctx.obj['PARAMS'].update(override)
            install_data.update(override)

        # Store the intall data in the context.
        # TODO: This is a terrible terrible mess.
        ctx.obj['PARAMS'].update(install_data)
        ctx.obj['PARAMS']['data'] = install_data

        # XXX: templates use treadmillid, but it is defined as "username" in
        #      cell object.
        ctx.obj['PARAMS']['treadmillid'] = ctx.obj['PARAMS'].get('username')

        os.environ['TREADMILL'] = distro

    return install
