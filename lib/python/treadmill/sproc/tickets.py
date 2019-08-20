"""Runs Treadmill App tickets service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import fnmatch
import logging
import os
import socket
import time
import tempfile

import click
import gssapi  # pylint: disable=import-error

from treadmill import appenv
from treadmill import context
from treadmill import endpoints
from treadmill import fs
from treadmill import subproc
from treadmill import supervisor
from treadmill import sysinfo
from treadmill import zknamespace as z
from treadmill import zkutils
from treadmill import dirwatch
from treadmill import cli
from treadmill.syscall import krb5
from treadmill.tickets import locker
from treadmill.tickets import receiver


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


def _configure_locker(tkt_spool_dir, scandir, cell, celluser):
    """Configure ticket forwarding service."""
    if os.path.exists(os.path.join(scandir, cell)):
        return

    _LOGGER.info('Configuring ticket locker: %s/%s', scandir, cell)
    name = cell
    realms = krb5.get_host_realm(sysinfo.hostname())
    krb5ccname = 'FILE:{tkt_spool_dir}/{celluser}@{realm}'.format(
        tkt_spool_dir=tkt_spool_dir,
        celluser=celluser,
        realm=realms[0],
    )
    supervisor.create_service(
        scandir,
        name=name,
        app_run_script=(
            '{treadmill}/bin/treadmill sproc '
            'tickets locker --tkt-spool-dir {tkt_spool_dir}'.format(
                treadmill=subproc.resolve('treadmill'),
                tkt_spool_dir=tkt_spool_dir
            )
        ),
        userid='root',
        environ_dir=os.path.join(scandir, name, 'env'),
        environ={
            'KRB5CCNAME': krb5ccname,
            'TREADMILL_CELL': cell,
        },
        downed=False,
        trace=None,
        monitor_policy=None
    )


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
    @click.option('--port', help='Receiver port.', default=0)
    @click.option('--appname', help='Pseudo app name to use for discovery',
                  required=True)
    @click.option('--endpoint', help='Pseudo endpoint to use for discovery',
                  default='tickets')
    @click.option('--keytab', help='List of keytabs to merge.',
                  multiple=True,
                  required=False)
    @click.option('--use-tktrecv', help='Run ticketreceiver protocol.',
                  is_flag=True, default=False)
    def accept_cmd(tkt_spool_dir, approot, port, appname, endpoint, keytab,
                   use_tktrecv):
        """Run ticket locker receiver."""
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
        # Unlike typical endpoint, we cannot make the node ephemeral as we
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

        if not use_tktrecv:
            subproc.safe_exec(['tkt_recv_v2',
                               '-p{}'.format(port),
                               '-d{}'.format(tkt_spool_dir)])
        else:
            _LOGGER.info('Running ticket receiver.')
            receiver.run_server(port, tkt_spool_dir)

    @top.command(name='monitor')
    @click.option('--tkt-spool-dir', help='Ticket spool directory.',
                  required=True)
    @click.option('--scandir', help='Supervisor scan directory.',
                  required=True)
    @click.option('--location', help='Location pattern to filter cells.',
                  required=False, envvar='TREADMILL_TKTFWD_CELLLOC')
    def monitor_cmd(tkt_spool_dir, scandir, location):
        """Configure ticket locker for each cell."""
        if location:
            _LOGGER.info('Using location filter: %s', location)
        else:
            _LOGGER.info('No location filter, configuring all cells.')

        admin_cell = context.GLOBAL.admin.cell()
        while True:
            for cell in admin_cell.list({}):
                celluser = cell['username']
                cellname = cell['_id']
                celllocation = cell.get('location', '')
                if location and not fnmatch.fnmatch(celllocation, location):
                    _LOGGER.info(
                        'Skip cell by location: %s %s', cellname, celllocation
                    )
                    continue

                _configure_locker(tkt_spool_dir, scandir, cellname, celluser)

            # TODO: need to stop/remove extra services. For now, extra
            #       services are removed on group restart.

            supervisor.control_svscan(scandir, (
                supervisor.SvscanControlAction.alarm,
                supervisor.SvscanControlAction.nuke
            ))
            time.sleep(60)

    @top.command(name='info')
    @click.option('--tkt-spool-dir', help='Ticket spool directory.',
                  required=True)
    @click.option('--tkt-info-dir', help='Ticket info directory.',
                  required=True)
    @click.option('--tkt-realms', help='List of supported kerberos realms.',
                  required=False, type=cli.LIST)
    def info_cmd(tkt_spool_dir, tkt_info_dir, tkt_realms):
        """Monitor tickets and dump ticket info as json file."""

        realms = krb5.get_host_realm(sysinfo.hostname())
        if tkt_realms:
            realms.extend(tkt_realms)

        def _is_valid(princ):
            if princ.startswith('.'):
                return False

            for realm in realms:
                if princ.endswith(realm):
                    return True

            return False

        def handle_tkt_event(tkt_file):
            """Handle ticket created event.
            """
            princ = os.path.basename(tkt_file)
            if not _is_valid(princ):
                return

            infofile = os.path.join(tkt_info_dir, princ)
            _LOGGER.info('Processing: %s', princ)
            try:
                os.environ['KRB5CCNAME'] = os.path.join(tkt_spool_dir, princ)
                creds = gssapi.creds.Credentials(usage='initiate')
                with open(infofile, 'wb') as f:
                    f.write(json.dumps({
                        'expires_at': int(time.time()) + creds.lifetime
                    }).encode())
            except gssapi.raw.GSSError as gss_err:
                fs.rm_safe(infofile)
            finally:
                del os.environ['KRB5CCNAME']

        def handle_tkt_delete(tkt_file):
            """Delete ticket info.
            """
            princ = os.path.basename(tkt_file)
            if not _is_valid(princ):
                return

            infofile = os.path.join(tkt_info_dir, princ)
            _LOGGER.info('Deleting: %s', princ)
            fs.rm_safe(infofile)

        watch = dirwatch.DirWatcher(tkt_spool_dir)
        watch.on_created = handle_tkt_event
        watch.on_deleted = handle_tkt_delete

        for tkt_file in os.listdir(tkt_spool_dir):
            handle_tkt_event(tkt_file)

        while True:
            if watch.wait_for_events(timeout=60):
                watch.process_events(max_events=100)

    del accept_cmd
    del monitor_cmd
    del locker_cmd
    del info_cmd

    return top
