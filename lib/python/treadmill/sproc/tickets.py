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

import fnmatch
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


_SERVERS_ACL = zkutils.make_role_acl('servers', 'rwcda')

_MIN_FWD_REFRESH = 5

_RENEW_INTERVAL = 60 * 60

_LOGGER = logging.getLogger(__name__)


def _renew_tickets(tkt_spool_dir, match):
    """Try and renew all tickets that match a pattern."""
    for tkt in glob.glob(os.path.join(tkt_spool_dir, match)):
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


def _reforward_ticket(ticket_file, endpoint, realm):
    """Forward ticket to self, potentially correcting ticket enc type."""
    _LOGGER.info('Before loopback forward: %s', ticket_file)
    subproc.call(['klist', '-e', '-5', ticket_file])

    subproc.call(['tkt-send', '--realm=%s' % realm,
                  '--endpoints=%s' % endpoint, '--timeout=5'],
                 environ={'KRB5CCNAME': 'FILE:' + ticket_file})

    _LOGGER.info('After loopback forward: %s', ticket_file)
    subproc.call(['klist', '-e', '-5', ticket_file])


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
    @click.option('--tkt-spool-dir',
                  help='Ticket spool directory.')
    @click.option('--port', help='Acceptor port.', default=0)
    @click.option('--appname', help='Pseudo app name to use for discovery',
                  required=True)
    @click.option('--endpoint', help='Pseudo endpoint to use for discovery',
                  default='tickets')
    def accept(tkt_spool_dir, port, appname, endpoint):
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
        subproc.safe_exec(['tkt-recv', 'tcp://*:%s' % port, tkt_spool_dir])

    @top.command()
    @click.option('--tkt-spool-dir',
                  help='Ticket spool directory.')
    @click.option('--with-loopback-forward', is_flag=True, default=False,
                  help='Forward tickets to self after renew')
    @click.option('--appname', help='Pseudo app name to use for discovery',
                  required=True)
    @click.option('--endpoint', help='Pseudo endpoint to use for discovery',
                  default='tickets')
    @click.option('--match', help='Filter ticktets that match the pattern.')
    @click.option('--realm', help='Realm of the ticket acceptor.',
                  required=True)
    def renew(tkt_spool_dir, with_loopback_forward, appname, endpoint, match,
              realm):
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

            if not fnmatch.fnmatch(ticket_file, match):
                _LOGGER.info('Ignore ticket: %s', ticket_file)
                return

            _LOGGER.info('Got new ticket: %s', ticket_file)

            if with_loopback_forward:
                # invoke tkt-send with KRB5CCNAME pointing to the new ticket
                # file.
                need_fwd = True
                try:
                    last_fwd_f = os.path.join(
                        os.path.dirname(path),
                        '.' + ticket_file + '.fwd'
                    )
                    mtime = os.stat(last_fwd_f).st_mtime
                    age = time.time() - mtime

                    if age < _MIN_FWD_REFRESH:
                        _LOGGER.info('Recent lock %s found, age: %s',
                                     last_fwd_f, age)
                        need_fwd = False
                except OSError as os_err:
                    _LOGGER.info('Last fwd file does not exist: %s - %s',
                                 last_fwd_f, os_err.errno)

                if need_fwd:
                    if endpoint_ref:
                        _reforward_ticket(path, endpoint_ref['endpoint'],
                                          realm)
                        utils.touch(last_fwd_f)
                    else:
                        _LOGGER.warning('Ticket endpoint not initialized.')
                else:
                    _LOGGER.info('Will not forward ticket: %s', ticket_file)

        watcher = dirwatch.DirWatcher(tkt_spool_dir)
        watcher.on_created = _on_created

        last_renew = 0
        while True:
            if (time.time() - last_renew) > _RENEW_INTERVAL:
                _renew_tickets(tkt_spool_dir, match)
                last_renew = time.time()

            if watcher.wait_for_events(timeout=60):
                watcher.process_events(max_events=10)

    del renew
    del accept
    del locker
    return top
