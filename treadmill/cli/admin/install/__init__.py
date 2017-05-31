"""Implementation of treadmill-admin-install CLI plugin."""
from __future__ import absolute_import

import os
import pkgutil
import sys
import yaml

import click

import treadmill
from treadmill import cli
from treadmill import context


__path__ = pkgutil.extend_path(__path__, __name__)


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_multi_command(__name__))
    @click.option('--install-dir', required=True,
                  help='Target installation directory.',
                  envvar='TREADMILL_APPROOT')
    @click.option('--cell', required=True, envvar='TREADMILL_CELL')
    @click.option('--config', required=False,
                  type=click.Path(exists=True, readable=True, allow_dash=True),
                  multiple=True)
    @click.option('--override', required=False, type=cli.DICT)
    @click.pass_context
    def install(ctx, install_dir, cell, config, override):
        """Installs Treadmill."""
        if cell == '-':
            cell = None

        if cell:
            context.GLOBAL.cell = cell
            context.GLOBAL.resolve(cell)

        ctx.obj['PARAMS'] = {
            'cell': cell,
            'zookeeper': context.GLOBAL.zk.url,
            'ldap': context.GLOBAL.ldap.url,
            'dns_domain': context.GLOBAL.dns_domain,
            'ldap_suffix': context.GLOBAL.ldap.ldap_suffix,
            'treadmill': treadmill.TREADMILL,
            'dir': install_dir,
        }

        for conf in config:
            if conf == '-':
                ctx.obj['PARAMS'].update(yaml.load(stream=sys.stdin))
            else:
                with open(conf, 'r') as fd:
                    ctx.obj['PARAMS'].update(yaml.load(stream=fd))

        if override:
            ctx.obj['PARAMS'].update(override)

        # XXX: hack - templates use treadmillid, but it is defined as
        #      "username" in cell object.
        ctx.obj['PARAMS']['treadmillid'] = ctx.obj['PARAMS'].get('username')

        os.environ['TREADMILL'] = treadmill.TREADMILL

    return install
