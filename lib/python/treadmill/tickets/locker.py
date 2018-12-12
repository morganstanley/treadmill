"""Ticket locker server."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import base64
import errno
import hashlib
import io
import logging
import os

import kazoo
import kazoo.client

from twisted.internet import reactor
from twisted.internet import protocol

from treadmill import gssapiprotocol
from treadmill import sysinfo
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils

_LOGGER = logging.getLogger(__name__)

_DIRWATCH_EVENTS_COUNT = 10


class TicketLocker:
    """Manages ticket exchange between ticket locker and the container."""

    def __init__(self, zkclient, tkt_spool_dir, trusted=None):
        self.zkclient = zkclient
        self.tkt_spool_dir = tkt_spool_dir
        self.zkclient.add_listener(zkutils.exit_on_lost)
        self.hostname = sysinfo.hostname()
        self.trusted = trusted
        if not self.trusted:
            self.trusted = {}

    def register_endpoint(self, port):
        """Register ticket locker endpoint in Zookeeper."""
        hostname = sysinfo.hostname()
        self.zkclient.ensure_path(z.TICKET_LOCKER)

        node_path = z.path.ticket_locker('%s:%s' % (hostname, port))
        _LOGGER.info('registering locker: %s', node_path)
        if self.zkclient.exists(node_path):
            _LOGGER.info('removing previous node %s', node_path)
            zkutils.ensure_deleted(self.zkclient, node_path)

        zkutils.put(self.zkclient, node_path, {}, acl=None, ephemeral=True)

    def close_zk_connection(self):
        """Close Zookeepeer connection."""
        self.zkclient.remove_listener(zkutils.exit_on_lost)
        zkutils.disconnect(self.zkclient)

    def process_request(self, princ, appname):
        """Process ticket request.

        - Assuming princ host/<hostname>@realm, extract the host name.
        - Read application name, and verify that the app indeed is placed on
          the host.
        - Read list of principals from the application manifest.
        - Send back ticket files for each princ, base64 encoded.
        """
        _LOGGER.info('Processing request from %s: %s', princ, appname)
        if not princ or not princ.startswith('host/'):
            _LOGGER.error('Host principal expected, got: %s.', princ)
            return None

        tkt_dict = dict()
        for ticket in self._get_app_tickets(princ, appname):
            tkt_file = os.path.join(self.tkt_spool_dir, ticket)
            try:
                with io.open(tkt_file, 'rb') as f:
                    encoded = base64.standard_b64encode(f.read())
                    tkt_dict[ticket] = encoded
            except (IOError, OSError) as err:
                if err.errno == errno.ENOENT:
                    _LOGGER.warning(
                        'Ticket file does not exist: %s', tkt_file
                    )
                else:
                    raise

        return tkt_dict

    def _get_app_tickets(self, princ, appname):
        """Get tickets required for the given app."""

        hostname = princ[len('host/'):princ.rfind('@')]

        if (hostname, appname) in self.trusted:
            tkts = self.trusted[(hostname, appname)]
            _LOGGER.info('Trusted app: %s/%s, tickets: %r',
                         hostname, appname, tkts)
            return tkts

        if not self.zkclient.exists(z.path.placement(hostname, appname)):
            _LOGGER.error('App %s not scheduled on node %s', appname, hostname)
            return set()

        try:
            appnode = z.path.scheduled(appname)
            app = zkutils.with_retry(zkutils.get, self.zkclient, appnode)

            return set(app.get('tickets', []))
        except kazoo.client.NoNodeError:
            _LOGGER.info('App does not exist: %s', appname)
            return set()


# Disable warning for too many branches.
# pylint: disable=R0912
def run_server(locker, register=True):
    """Runs tickets server."""
    _LOGGER.info('Tickets server starting.')

    # no __init__ method.
    #
    # pylint: disable=W0232
    class TicketLockerServer(gssapiprotocol.GSSAPILineServer):
        """Ticket locker server."""

        @utils.exit_on_unhandled
        def got_line(self, data):
            """Invoked after authentication is done, decrypted data as arg.

            :param ``bytes`` data:
                Data received from the client.
            """
            appname = data.decode()
            tkts = locker.process_request(self.peer(), appname)
            if tkts:
                _LOGGER.info('Sending tickets for: %r', tkts.keys())
                for princ, encoded in tkts.items():
                    if encoded:
                        _LOGGER.info('Sending ticket: %s:%s',
                                     princ,
                                     hashlib.sha1(encoded).hexdigest())
                        self.write(b':'.join((princ.encode(), encoded)))
                    else:
                        _LOGGER.info('Sending ticket %s:None', princ)
                        self.write(b':'.join((princ.encode(), b'')))
            else:
                _LOGGER.info('No tickets found for app: %s', appname)

            self.write(b'')

    class TicketLockerServerFactory(protocol.Factory):
        """TicketLockerServer factory."""

        def buildProtocol(self, addr):  # pylint: disable=C0103
            return TicketLockerServer()

    port = reactor.listenTCP(0, TicketLockerServerFactory()).getHost().port

    _LOGGER.info('Running ticket locker on port: %s', port)
    if register:
        locker.register_endpoint(port)
    reactor.run()
