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
    @click.option('--aliases', required=True,
                  type=click.Path(exists=True, readable=True),
                  multiple=True)
    @click.option('--config', required=False,
                  type=click.Path(exists=True, readable=True, allow_dash=True),
                  multiple=True)
    @click.option('--override', required=False, type=cli.DICT)
    @click.pass_context
    def install(ctx, install_dir, cell, aliases, config, override):
        """Installs Treadmill."""
        if cell == '-':
            cell = None

        if cell:
            context.GLOBAL.cell = cell
            context.GLOBAL.resolve(cell)

        path_list = []
        aliases_data = {}
        for conf in aliases:
            with open(conf, 'r') as fd:
                path_list.append(os.path.abspath(fd.name))
                aliases_data.update(yaml.load(fd.read()))

        aliases_path = ":".join(path_list)

        ctx.obj['PARAMS'] = {
            'aliases_path': aliases_path,
            'cell': cell,
            'zookeeper': context.GLOBAL.zk.url,
            'ldap': context.GLOBAL.ldap.url,
            'dns_domain': context.GLOBAL.dns_domain,
            'ldap_search_base': context.GLOBAL.ldap.search_base,
            'treadmill': treadmill.TREADMILL,
            'dir': install_dir,
        }

        ctx.obj['PARAMS']['_alias'] = aliases_data
        # TODO(boysson): remove the below once all templates are cleaned up
        ctx.obj['PARAMS'].update(aliases_data)

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
        os.environ['TREADMILL_ALIASES_PATH'] = aliases_path

    return install
