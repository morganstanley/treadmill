"""Installs and configures Treadmill locally."""

import os

import click
import yaml

import treadmill

from treadmill import context
from treadmill import admin
from treadmill.osmodules import bootstrap
from treadmill import cli


def _load_configs(config, default_file):
    allconfigs = [
        os.path.join(treadmill.TREADMILL, 'etc/linux.exe.config'),
        os.path.join(treadmill.TREADMILL, default_file)
    ]

    for filename in config:
        allconfigs.append(filename)

    params = {}
    for filename in allconfigs:
        with open(filename) as f:
            params.update(yaml.load(f.read()))

    return params

def _load_ldap_config():
    """Parameters for both node and master."""
    cellname = context.GLOBAL.cell
    admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
    return {
        'cell': cellname,
        'zookeeper': context.GLOBAL.zk.url,
        'ldap': context.GLOBAL.ldap.url,
        'dns_domain': context.GLOBAL.dns_domain,
        'ldap_search_base': context.GLOBAL.ldap.search_base,
        'treadmill': treadmill.TREADMILL,
        'treadmillid': params['username']
    }


def init():
    """Return top level command handler."""

    @click.group()

    @click.option('--zookeeper', required=False,
                  envvar='TREADMILL_ZOOKEEPER',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.pass_context
    def install(ctx):
        """Installs Treadmill."""
        pass

    @install.command()
    @click.option('--install-dir',
                  default=lambda: os.path.join(bootstrap.default_install_dir(),
                                               "treadmill"))
    @click.option('--run/--no-run', is_flag=True, default=False)
    @click.option('--config', type=click.File(), multiple=True)
    @click.option('--use-ldap', is_flag=True, default=False)
    @click.pass_context
    def node(ctx, install_dir, run, config, use_ldap):
        """Installs Treadmill node."""

        node_config = 'local/linux/node.config.yml'
        params = _load_configs(config, node_config)

        params.update({'dir': install_dir})

        if use_ldap:
            params.update(_load_ldap_config())

        node_bootstrap = bootstrap.NodeBootstrap(
            install_dir,
            params,
        )

        node_bootstrap.install()

        if run:
            node_bootstrap.run()

    del node

    if os.name != 'nt':
        @install.command()
        @click.option('--install-dir',
                      default=lambda: os.path.join(
                      bootstrap.default_install_dir(),
                      "treadmill_master"))
        @click.option('--run/--no-run', is_flag=True, default=False)
        @click.option('--master-id', required=True,
                      type=click.Choice(['1', '2', '3']))
        @click.option('--config', type=click.File(), multiple=True)
        @click.option('--use-ldap', is_flag=True, default=False)
        @click.pass_context
        def master(ctx, install_dir, run, master_id, config, use_ldap):
            """Installs Treadmill master."""

            master_config_file = 'local/linux/master.config.yml'

            params = _load_configs(config, master_config_file)
            if use_ldap:
                params.update(_load_ldap_config())


            params.update({
                'master-id': master_id,
                'dir': os.path.join(
                    install_dir,
                    os.environ.get('TREADMILL_CELL'),
                    master_id)
            })
            for master in params['masters']:  # pylint: disable=E1136
                if master['idx'] == int(master_id):
                    params.update({'me': master})

            master_bootstrap = bootstrap.MasterBootstrap(
                install_dir,
                params,
                master_id
            )
            master_bootstrap.install()

            if run:
                master_bootstrap.run()

        del master

    return install
