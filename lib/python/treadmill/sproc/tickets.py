"""Runs Treadmill App tickets service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import socket
import time
import tempfile

import click

from treadmill import appenv
from treadmill import endpoints
from treadmill import fs
from treadmill.tickets import locker
from treadmill import context
from treadmill import zknamespace as z
from treadmill import subproc
from treadmill import sysinfo
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)


def _construct_keytab(keytabs):
    """Construct keytab from the list."""
    temp_keytabs = []
    file_keytabs = []
    for kt_uri in keytabs:
        if kt_uri.startswith('zookeeper:'):
            zkpath = kt_uri[len('zookeeper:'):]
            with tempfile.NamedTemporaryFile(mode='wb', delete=False) as temp:
                ktab, _metadata = context.GLOBAL.zk.conn.get(zkpath)
                temp.write(ktab)
                temp_keytabs.append(temp.name)

        if kt_uri.startswith('file:'):
            file_keytabs.append(kt_uri[len('file:'):])

    kt_target = os.environ.get('KRB5_KTNAME')
    cmd_line = ['kt_add', kt_target] + temp_keytabs + file_keytabs
    subproc.check_call(cmd_line)

    for temp_keytab in temp_keytabs:
        fs.rm_safe(temp_keytab)


def init():
    """Top level command handler."""
    # pylint: disable=too-many-statements

    @click.group()
    def top():
        """Manage Kerberos tickets.
        """

    @top.command(name='locker')
    @click.option('--tkt-spool-dir',
                  help='Ticket spool directory.')
    @click.option('--trusted', type=(str, str, str),
                  help="Trusted app (princ, app, tkt1[,tkt2,...])",
                  multiple=True)
    @click.option('--no-register', is_flag=True, default=False,
                  help='Do no register in Zookeeper.')
    def locker_cmd(tkt_spool_dir, trusted, no_register):
        """Run ticket locker daemon."""
        trusted_apps = {}
        for hostname, app, tkts in trusted:
            tkts = list(set(tkts.split(',')))
            _LOGGER.info('Trusted: %s/%s : %r', hostname, app, tkts)
            trusted_apps[(hostname, app)] = tkts

        tkt_locker = locker.TicketLocker(
            context.GLOBAL.zk.conn,
            tkt_spool_dir,
            trusted=trusted_apps
        )
        locker.run_server(tkt_locker, register=(not no_register))

    @top.command(name='accept')
    @click.option('--tkt-spool-dir',
                  help='Ticket spool directory.')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--port', help='Acceptor port.', default=0)
    @click.option('--appname', help='Pseudo app name to use for discovery',
                  required=True)
    @click.option('--endpoint', help='Pseudo endpoint to use for discovery',
                  default='tickets')
    @click.option('--keytab', help='List of keytabs to merge.',
                  multiple=True,
                  required=False)
    def accept_cmd(tkt_spool_dir, approot, port, appname, endpoint, keytab):
        """Run ticket locker acceptor."""
        if keytab:
            _construct_keytab(keytab)

        if port == 0:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', 0))
            port = sock.getsockname()[1]
            sock.close()

        hostname = sysinfo.hostname()
        hostport = '%s:%s' % (hostname, port)

        endpoint_proid_path = z.path.endpoint_proid(appname)
        acl = context.GLOBAL.zk.conn.make_servers_acl()
        _LOGGER.info(
            'Ensuring %s exists with ACL %r',
            endpoint_proid_path,
            acl
        )
        zkutils.ensure_exists(
            context.GLOBAL.zk.conn,
            endpoint_proid_path,
            acl=[acl]
        )

        endpoint_path = z.path.endpoint(appname, 'tcp', endpoint)
        _LOGGER.info('Registering %s %s', endpoint_path, hostport)

        # Need to delete/create endpoints for the disovery to pick it up in
        # case of master restart.
        #
        # Unlile typical endpoint, we cannot make the node ephemeral as we
        # exec into tkt-recv.
        zkutils.ensure_deleted(context.GLOBAL.zk.conn, endpoint_path)
        time.sleep(5)
        zkutils.put(context.GLOBAL.zk.conn, endpoint_path, hostport)

        context.GLOBAL.zk.conn.stop()

        # TODO: this will publish information about the endpoint state
        #       under /discovery. Once discovery is refactored (if it will be)
        #       we can remove the "manual" zookeeper manipulation.
        tm_env = appenv.AppEnvironment(approot)
        endpoints_mgr = endpoints.EndpointsMgr(tm_env.endpoints_dir)
        endpoints_mgr.unlink_all(
            appname=appname,
            endpoint=endpoint,
            proto='tcp'
        )
        endpoints_mgr.create_spec(
            appname=appname,
            endpoint=endpoint,
            proto='tcp',
            real_port=port,
            pid=os.getpid(),
            port=port,
            owner='/proc/{}'.format(os.getpid()),
        )

        subproc.safe_exec(['tkt_recv_v2',
                           '-p{}'.format(port),
                           '-d{}'.format(tkt_spool_dir)])

    del accept_cmd
    del locker_cmd
    return top
