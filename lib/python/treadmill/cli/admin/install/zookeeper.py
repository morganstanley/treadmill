"""Installs and configures Zookeeper locally.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import click

from treadmill import bootstrap
from treadmill import context

_LOGGER = logging.getLogger(__name__)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--run/--no-run', is_flag=True, default=False)
    @click.option('--master-id', required=True,
                  type=click.Choice(['1', '2', '3']))
    @click.option('--data-dir', required=False,
                  type=click.Path(exists=True),
                  envvar='TREADMILL_ZOOKEEPER_DATA_DIR',
                  help='Zookeeper data directory.')
    @click.option('--krb-realm', help='Kerberos realm',
                  envvar='TREADMILL_KRB_REALM',
                  required=True)
    @click.pass_context
    def zookeeper(ctx, run, master_id, data_dir, krb_realm):
        """Installs Treadmill master."""

        ctx.obj['PARAMS']['zookeeper'] = context.GLOBAL.zk.url
        ctx.obj['PARAMS']['ldap'] = context.GLOBAL.ldap.url
        ctx.obj['PARAMS']['master_id'] = master_id
        ctx.obj['PARAMS']['krb_realm'] = krb_realm
        if data_dir:
            ctx.obj['PARAMS']['data_dir'] = data_dir
        dst_dir = ctx.obj['PARAMS']['dir']
        profile = ctx.obj['PARAMS'].get('profile')

        for master in ctx.obj['PARAMS']['masters']:  # pylint: disable=E1136
            if int(master['idx']) == int(master_id):
                ctx.obj['PARAMS'].update({'me': master})

        run_sh = None
        if run:
            run_sh = os.path.join(dst_dir, 'treadmill', 'bin', 'run.sh')

        bootstrap.install(
            'zookeeper',
            dst_dir,
            ctx.obj['PARAMS'],
            run=run_sh,
            profile=profile,
        )

    return zookeeper
