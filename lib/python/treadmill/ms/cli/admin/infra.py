"""Admin infra CLI module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import logging
import time
import tempfile

import click
import jinja2
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import admin
from treadmill import cli
from treadmill import context

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import zapp


_ONE_MIN = 60
_LDAPMODIFY = '/ms/dist/fsf/PROJ/openldap/2.4.45-0/exec/bin/ldapmodify'

_LOGGER = logging.getLogger(__name__)


def _rm_ldap_list(ldap_list, server, port):
    """Remove a given server from a list"""
    if not server.startswith('ldap://'):
        server = 'ldap://{}:{}'.format(server, port)

    try:
        ldap_list.remove(server)
    except ValueError:
        pass

    return ldap_list


def _ldif_modify(action, ldap_list, server, port, rid):
    """Load LDIF template and create temp file"""
    jinja_env = jinja2.Environment(loader=jinja2.PackageLoader(__name__))
    template = jinja_env.get_template('ldap_modify_repl.ldif')

    tmpl_vars = dict(
        server=server,
        port=port,
        action=action,
        rid=rid,
    )
    ldif = template.render(tmpl_vars)

    servers = _rm_ldap_list(ldap_list, server, port)
    _LOGGER.debug('servers: %r', servers)

    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(ldif)

    cmd = [
        _LDAPMODIFY,
        '-Q', '-YGSSAPI',
        '-H', servers[0],
        '-f', f.name,
    ]
    _LOGGER.debug('%s', ' '.join(cmd))

    output = subprocess.check_output(cmd)
    _LOGGER.debug('output: %r', output)


def _get_repls(ldap_list):
    """Get all the replication servers in config"""
    ldap = ldap_list[0]

    ldap_admin = admin.Admin(ldap, '')
    ldap_admin.connect()

    return ldap_admin.get_repls()


def _exists_in_repl(repls, server):
    """LDAP server exists in replication list"""
    for repl in repls:
        if server in repl:
            return True

    return False


def ldap_group(parent):
    """LDAP group"""

    @parent.group(name='ldap')
    @click.option('--cell', required=False,
                  envvar='TREADMILL_CELL',
                  is_eager=True, callback=cli.handle_context_opt,
                  expose_value=False)
    @click.pass_context
    def ldap_grp(ctx):
        """Manage regional infra"""
        ctx.obj = dict(cell=context.GLOBAL.cell)

    @ldap_grp.command(name='show-repl')
    @click.option('--ldap-list', help='LDAP list',
                  envvar='TREADMILL_LDAP_LIST',
                  required=True, type=cli.LIST)
    def show_ldap_repl(ldap_list):
        """Show replication config"""
        repls = _get_repls(ldap_list)

        if not repls:
            cli.bad_exit('No replication is setup in the MDB config')

        for repl in sorted(repls):
            cli.out(repl)

    @ldap_grp.command(name='add-repl')
    @click.option('--plant', help='Zapp plant id', required=True)
    @click.option('--server', help='LDAP server name', required=True)
    @click.option('--port', help='LDAP port', required=True)
    @click.option('--rid', help='LDAP rid in mdb', required=True)
    @click.option('--ldap-list', help='LDAP list',
                  envvar='TREADMILL_LDAP_LIST',
                  required=True, type=cli.LIST)
    @click.pass_context
    def add_ldap_repl(ctx, plant, server, port, rid, ldap_list):
        """Add LDAP to replication quorum"""
        if not plant:
            plant = zapp.cell2plant(ctx.obj['cell'])
        zapp_client = zapp.Zapp(None, plant)

        if not zapp_client.ldap_app_exists(server, port):
            cli.bad_exit(
                'You must have the LDAP app inserted into the Zapp data '
                'model for %s, before you can add it to replication', plant
            )

        _LOGGER.info('Stopping %s:%s in Zapp', server, port)
        zapp_client.stop_ldap(server, port)

        repls = _get_repls(ldap_list)

        if _exists_in_repl(repls, server):
            cli.bad_exit(
                'Replication server %s is already in the MDB config!', server
            )

        _LOGGER.info('Stopping %s:%s in Zapp', server, port)
        zapp_client.backup_ldap(server, port)

        _LOGGER.info('Starting %s:%s in Zapp', server, port)
        zapp_client.start_ldap(server, port)

        _LOGGER.info('Waiting for LDAP to come back up...')
        # TODO: add a loop check to a telnet check on server:port
        time.sleep(_ONE_MIN)

        _LOGGER.info(
            'Adding %s:%s rid=%s to LDAP sync replication',
            server, port, rid
        )
        _ldif_modify('add', ldap_list, server, port, rid)

    @ldap_grp.command(name='del-repl')
    @click.option('--plant', help='Zapp plant id', required=True)
    @click.option('--server', help='LDAP server name', required=True)
    @click.option('--port', help='LDAP port', required=True)
    @click.option('--rid', help='LDAP rid in mdb', required=True)
    @click.option('--ldap-list', help='LDAP list',
                  envvar='TREADMILL_LDAP_LIST',
                  required=True, type=cli.LIST)
    @click.pass_context
    def del_ldap_repl(ctx, plant, server, port, rid, ldap_list):
        """Delete LDAP from replication quorum"""
        if not plant:
            plant = zapp.cell2plant(ctx.obj['cell'])
        zapp_client = zapp.Zapp(None, plant)

        if not zapp_client.ldap_app_exists(server, port):
            cli.bad_exit(
                'You must have the LDAP app inserted into the Zapp data '
                'model for %s, before you can add it to replication', plant
            )

        _LOGGER.info('Stopping %s:%s in Zapp', server, port)
        zapp_client.stop_ldap(server, port)

        _LOGGER.info(
            'Deleting %s:%s rid=%s from LDAP sync replication',
            server, port, rid
        )
        _ldif_modify('delete', ldap_list, server, port, rid)

    del show_ldap_repl
    del add_ldap_repl
    del del_ldap_repl


def init():
    """Admin infra CLI module"""

    @click.group(name='infra')
    def infra_group():
        """Manage regional infra"""
        pass

    ldap_group(infra_group)

    return infra_group
