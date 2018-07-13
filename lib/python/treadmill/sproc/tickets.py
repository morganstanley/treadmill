"""Runs Treadmill App tickets service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# TODO: This service should be refactored into two:
#                - node service refreshing tickets for all apps, stoing in
#                  /tmp
#                - container specific, running on mount namespace of the
#                  container, copy tickets from /tmp to /var/spool/tickets
#                  of the container.

import glob
import logging
import os
import socket
import time
import tempfile

import click

from treadmill import appenv
from treadmill import endpoints
from treadmill import fs
from treadmill import tickets
from treadmill import context
from treadmill import zknamespace as z
from treadmill import subproc
from treadmill import sysinfo
from treadmill import zkutils
from treadmill import dirwatch
from treadmill import utils
from treadmill import cli


_MIN_FWD_REFRESH = 5

_RENEW_INTERVAL = 60 * 60

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


def _renew_tickets(tkt_spool_dir):
    """Try and renew all tickets that match a pattern."""
    for tkt in glob.glob(os.path.join(tkt_spool_dir, '*')):
        if tkt.startswith('.'):
            continue

        _LOGGER.info('Renew ticket: %s', tkt)
        try:
            subproc.check_call(
                ['kinit', '-R'],
                environ={'KRB5CCNAME': 'FILE:' + tkt},
            )
            _LOGGER.info('Tickets renewed successfully.')
        except subproc.CalledProcessError as err:
            _LOGGER.info('Tickets not renewable, kinit rc: %s',
                         err.returncode)
        except OSError as os_err:
            _LOGGER.warning('Error renewing tickets: %s', os_err)

        subproc.call(['klist', '-e', '-5', tkt])


def _reforward_ticket(ticket_file, tkt_final_dir, endpoint):
    """Forward ticket to self, potentially correcting ticket enc type."""
    _LOGGER.info('Reforwarding to: %s', endpoint)
    _LOGGER.info('Before loopback forward: %s', ticket_file)
    subproc.call(['klist', '-e', '-5', ticket_file])

    host, port = endpoint.split(':')
    subproc.call(['tkt_send_v2',
                  '-h{}'.format(host),
                  '-p{}'.format(port)],
                 environ={'KRB5CCNAME': 'FILE:' + ticket_file})

    final_tkt_path = os.path.join(tkt_final_dir,
                                  os.path.basename(ticket_file))
    _LOGGER.info('After loopback forward: %s', final_tkt_path)
    subproc.call(['klist', '-e', '-5', final_tkt_path])


def init():
    """Top level command handler."""

    @click.group()
    def top():
        """Manage Kerberos tickets."""
        pass

    @top.command()
    @click.option('--tkt-spool-dir',
                  help='Ticket spool directory.')
    @click.option('--trusted', type=(str, str, str),
                  help="Trusted app (princ, app, tkt1[,tkt2,...])",
                  multiple=True)
    @click.option('--no-register', is_flag=True, default=False,
                  help='Do no register in Zookeeper.')
    def locker(tkt_spool_dir, trusted, no_register):
        """Run ticket locker daemon."""
        trusted_apps = {}
        for hostname, app, tkts in trusted:
            tkts = list(set(tkts.split(',')))
            _LOGGER.info('Trusted: %s/%s : %r', hostname, app, tkts)
            trusted_apps[(hostname, app)] = tkts
        tkt_locker = tickets.TicketLocker(context.GLOBAL.zk.conn,
                                          tkt_spool_dir,
                                          trusted=trusted_apps)
        tickets.run_server(tkt_locker, register=(not no_register))

    @top.command()
    @click.option('--appname', required=True,
                  help='Treadmill app name.')
    @click.option('--tkt-spool-dir',
                  help='Ticket spool directory.',
                  required=True)
    @click.option('--lockers', help='List of locker host:port',
                  type=cli.LIST)
    @click.option('--sleep', type=int, help='Sleep interval.',
                  default=_RENEW_INTERVAL)
    def fetch(appname, tkt_spool_dir, lockers, sleep):
        """Fetch ticket for given app."""
        while True:
            if not lockers:
                lockers = tickets.lockers(context.GLOBAL.zk.conn)

            for locker in lockers:
                host, port = locker.split(':')
                tickets.request_tickets_from(
                    host, port, appname, tkt_spool_dir
                )
            # Invoking with --sleep 0 will fetch tickets once and exit.
            if not sleep:
                break
            time.sleep(sleep)

    @top.command()
    @click.option('--tkt-spool-dir', help='Ticket spool directory.',
                  required=True)
    @click.option('--realms', help='Valid ticket realms.', type=cli.LIST,
                  required=True)
    def publish(tkt_spool_dir, realms):
        """Run ticket locker daemon."""
        tkt_locker = tickets.TicketLocker(context.GLOBAL.zk.conn,
                                          tkt_spool_dir)
        tkt_locker.publish_tickets(realms)

    @top.command()
    @click.option('--tkt-spool-dir',
                  help='Ticket spool directory.')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--port', help='Acceptor port.', default=0)
    @click.option('--appname', help='Pseudo app name to use for discovery',
                  required=True)
    @click.option('--endpoint', help='Pseudo endpoint to use for discovery',
                  default='tickets')
    @click.option('--use-v2', help='Start tkt-recv v2 protocol.', is_flag=True,
                  default=False)
    @click.option('--keytab', help='List of keytabs to merge.',
                  multiple=True,
                  required=False)
    def accept(tkt_spool_dir, approot, port, appname, endpoint, use_v2,
               keytab):
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

        # Exec into tickets acceptor. If race condition will not allow it to
        # bind to the provided port, it will exit and registration will
        # happen again.
        if use_v2:
            subproc.safe_exec(['tkt_recv_v2',
                               '-p{}'.format(port),
                               '-d{}'.format(tkt_spool_dir)])
        else:
            subproc.safe_exec(['tkt_recv',
                               'tcp://*:{}'.format(port),
                               tkt_spool_dir])

    @top.command()
    @click.option('--tkt-spool-dir',
                  help='Ticket spool directory.')
    @click.option('--tkt-final-dir',
                  help='Ticket final spool directory.')
    @click.option('--appname', help='Pseudo app name to use for discovery',
                  required=True)
    @click.option('--endpoint', required=True,
                  help='Forward tickets to endpoint after renew')
    @click.option('--realms', required=False,
                  type=cli.LIST,
                  help='Valid ticket realms.')
    def reforward(tkt_spool_dir, tkt_final_dir, appname, endpoint, realms):
        """Renew tickets in the locker."""

        endpoint_ref = {}
        endpoint_path = z.path.endpoint(appname, 'tcp', endpoint)

        _LOGGER.info('Starting ticket renew process, ticket endpoint: %s',
                     endpoint_path)

        zkclient = context.GLOBAL.zk.conn

        @zkclient.DataWatch(endpoint_path)
        @utils.exit_on_unhandled
        def _tickets_endpoint_watch(data, _stat, event):
            """Watch to endpoint changes."""
            if data is None and event is None:
                # The node is not there yet, wait.
                _LOGGER.info('Ticket endpoint missing: %s', endpoint_path)
                endpoint_ref.clear()
            elif event is not None and event.type == 'DELETED':
                _LOGGER.info('Ticket endpoint node deleted.')
                endpoint_ref.clear()
            else:
                _LOGGER.info('Ticket endpoint initialized: %s', data)
                endpoint_ref['endpoint'] = data.decode('utf-8')

            return True

        def _on_created(path):
            """Callback invoked with new ticket appears."""
            ticket_file = os.path.basename(path)
            if ticket_file.startswith('.'):
                return

            # TODO: this is for hotfix only. Ticker receiver creates temp
            #       ticket file with random suffix, not with . prefix.
            #
            #       As result, thie core is invoked for tmp files, and not
            #       only it generates too much traffic for ticket receiver,
            #       but it also generates errors, because by the time we
            #       forward cache is gone.
            #
            #       Proper soltution for ticket receiver to create temp files
            #       starting with dot.
            valid_realm = False
            for realm in realms:
                if ticket_file.endswith(realm):
                    valid_realm = True
                    break

            if not valid_realm:
                return

            _LOGGER.info('Got new ticket: %s', ticket_file)

            if endpoint_ref:
                # invoke tkt-send with KRB5CCNAME pointing to the new ticket
                # file.
                _reforward_ticket(path,
                                  tkt_final_dir,
                                  endpoint_ref['endpoint'])
            else:
                _LOGGER.warning('No ticket endpoint found.')

        watcher = dirwatch.DirWatcher(tkt_spool_dir)
        watcher.on_created = _on_created

        # Make sure to forward all tickets on startup
        tickets_in_tmp_spool = set([
            os.path.basename(path)
            for path in glob.glob(os.path.join(tkt_spool_dir, '*'))
        ])
        tickets_in_dst_spool = set([
            os.path.basename(path)
            for path in glob.glob(os.path.join(tkt_final_dir, '*'))
        ])

        for common in tickets_in_tmp_spool & tickets_in_dst_spool:
            dst_path = os.path.join(tkt_final_dir, common)
            tmp_path = os.path.join(tkt_spool_dir, common)
            try:
                dst_ctime = os.stat(dst_path).st_ctime
                tmp_ctime = os.stat(tmp_path).st_ctime

                if tmp_ctime > dst_ctime:
                    _LOGGER.info('Ticket in spool out of date: %s', common)
                    _on_created(tmp_path)
                else:
                    _LOGGER.info('Ticket: %s is up to date.', common)

            except OSError:
                _on_created(tmp_path)

        for missing in tickets_in_tmp_spool - tickets_in_dst_spool:
            _LOGGER.info('Forwarding missing ticket: %s', missing)
            _on_created(os.path.join(tkt_spool_dir, missing))

        _LOGGER.info('Watching for events.')
        while True:
            if watcher.wait_for_events(timeout=60):
                watcher.process_events(max_events=10)

    @top.command()
    @click.option('--tkt-spool-dir',
                  help='Ticket spool directory.')
    def renew(tkt_spool_dir):
        """Renew tickets in the locker."""

        while True:
            time.sleep(_RENEW_INTERVAL)
            _renew_tickets(tkt_spool_dir)

    del reforward
    del renew
    del accept
    del locker
    del publish
    return top
