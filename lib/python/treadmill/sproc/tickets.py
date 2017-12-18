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

import click
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import tickets
from treadmill import context
from treadmill import zknamespace as z
from treadmill import subproc
from treadmill import sysinfo
from treadmill import zkutils
from treadmill import dirwatch
from treadmill import utils
from treadmill import cli


_SERVERS_ACL = zkutils.make_role_acl('servers', 'rwcda')

_MIN_FWD_REFRESH = 5

_RENEW_INTERVAL = 60 * 60

_LOGGER = logging.getLogger(__name__)


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
        except subprocess.CalledProcessError as err:
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
    def locker(tkt_spool_dir):
        """Run ticket locker daemon."""
        tkt_locker = tickets.TicketLocker(context.GLOBAL.zk.conn,
                                          tkt_spool_dir)
        tickets.run_server(tkt_locker)

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
    @click.option('--port', help='Acceptor port.', default=0)
    @click.option('--appname', help='Pseudo app name to use for discovery',
                  required=True)
    @click.option('--endpoint', help='Pseudo endpoint to use for discovery',
                  default='tickets')
    @click.option('--use-v2', help='Start tkt-recv v2 protocol.', is_flag=True,
                  default=False)
    def accept(tkt_spool_dir, port, appname, endpoint, use_v2):
        """Run ticket locker acceptor."""
        if port == 0:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', 0))
            port = sock.getsockname()[1]
            sock.close()

        hostname = sysinfo.hostname()
        hostport = '%s:%s' % (hostname, port)

        endpoint_proid_path = z.path.endpoint_proid(appname)
        _LOGGER.info('Ensuring %s exists with ACL %r',
                     endpoint_proid_path, _SERVERS_ACL)
        zkutils.ensure_exists(context.GLOBAL.zk.conn, endpoint_proid_path,
                              acl=[_SERVERS_ACL])

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
                endpoint_ref['endpoint'] = data

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
