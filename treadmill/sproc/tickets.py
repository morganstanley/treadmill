"""Runs Treadmill App tickets service."""


# TODO: This service should be refactored into two:
#                - node service refreshing tickets for all apps, stoing in
#                  /tmp
#                - container specific, running on mount namespace of the
#                  container, copy tickets from /tmp to /var/spool/tickets
#                  of the container.

import logging
import socket
import time

import click

from .. import tickets
from .. import context
from .. import zknamespace as z
from .. import subproc
from .. import sysinfo
from .. import zkutils


_SERVERS_ACL = zkutils.make_role_acl('servers', 'rwcd')

_LOGGER = logging.getLogger(__name__)


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
                  default=tickets)
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

    del accept
    del locker
    return top
