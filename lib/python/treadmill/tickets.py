"""Handles ticket forwarding from the ticket master to the node.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import base64
import errno
import glob
import hashlib
import io
import logging
import os
import random
import shutil
import stat
import tempfile
import time

import kazoo
import kazoo.client

from twisted.internet import reactor
from twisted.internet import protocol

import six

from treadmill import fs
from treadmill import dirwatch
from treadmill import gssapiprotocol
from treadmill import subproc
from treadmill import sysinfo
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils

_LOGGER = logging.getLogger(__name__)

_STALE_TKTS_PRUNE_INTERVAL = 60

_DIRWATCH_EVENTS_COUNT = 10


class Ticket:
    """Helper class to manage krb ticket.

    princ - fully qualified kerberos principal uid@realm.
    ticket - base64 encoded ticket.
    """

    def __init__(self, princ, ticket):
        self.princ = princ
        self.ticket = ticket
        user = princ[:princ.find('@') if '@' in princ else len(princ)]
        try:
            self.uid = utils.get_uid_gid(user)[0]
        except KeyError:
            _LOGGER.warning('princ/user does not exist: %s', user)
            self.uid = None

    def __repr__(self):
        ticket_cs = None
        if self.ticket:
            ticket_cs = hashlib.sha1(self.ticket).hexdigest()
        return 'Ticket(princ=%s, ticket=%s)' % (self.princ, ticket_cs)

    def __unicode__(self):
        """Returns printable info about the ticket"""
        if self.ticket:
            return 'Ticket: %s, %s' % (self.princ,
                                       hashlib.sha1(self.ticket).hexdigest())
        else:
            return 'Ticket: %s, null'

    def __eq__(self, other):
        return self.princ == other.princ and self.ticket == other.ticket

    def write(self, path=None):
        """Writes the ticket to <path>/<princ>."""
        if path is None:
            path = self.tkt_path

        _LOGGER.info('Writing ticket: %s', path)
        # TODO: confirm the comment or rewrite using fs.write_safe.
        #
        # The following code will write ticket to destination only of the
        # ticket is valid.
        #
        # If the ticket is not valid, destination file is not touched.
        #
        # It is not clear if it is a good fit for fs.write_safe.
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(path),
                                         prefix='.tmp' + self.princ,
                                         delete=False,
                                         mode='wb') as tkt_file:

            try:
                # Write the file
                tkt_file.write(self.ticket)
                # Set the owner
                if self.uid is not None:
                    os.fchown(tkt_file.fileno(), self.uid, -1)
                # TODO: Should we enforce the mode too?
                tkt_file.flush()

                # Only write valid tickets.
                if krbcc_ok(tkt_file.name):
                    os.rename(tkt_file.name, path)
                else:
                    _LOGGER.warning('Invalid or expired ticket: %s',
                                    tkt_file.name)
                    return False
            except (IOError, OSError):
                _LOGGER.exception('Error writing ticket file: %s', path)
                return False
            finally:
                fs.rm_safe(tkt_file.name)

        return True

    def copy(self, dst, src=None):
        """Atomically copy tickets to destination."""
        if src is None:
            src = self.tkt_path

        dst_dir = os.path.dirname(dst)
        with io.open(src, 'rb') as tkt_src_file:
            # TODO; rewrite as fs.write_safe.
            with tempfile.NamedTemporaryFile(dir=dst_dir,
                                             prefix='.tmp' + self.princ,
                                             delete=False,
                                             mode='wb') as tkt_dst_file:
                try:
                    # Copy binary from source to dest
                    shutil.copyfileobj(tkt_src_file, tkt_dst_file)
                    # Set the owner
                    if self.uid is not None:
                        os.fchown(tkt_dst_file.fileno(), self.uid, -1)
                    # Copy the mode
                    src_stat = os.fstat(tkt_src_file.fileno())
                    os.fchmod(tkt_dst_file.fileno(),
                              stat.S_IMODE(src_stat.st_mode))
                    tkt_dst_file.flush()
                    os.rename(tkt_dst_file.name, dst)

                except (IOError, OSError):
                    _LOGGER.exception('Error copying ticket from %s to %s',
                                      src, dst)
                finally:
                    fs.rm_safe(tkt_dst_file.name)

    def renew(self):
        """Runs kinit -R against the existing CCNAME."""
        if not os.path.exists(self.tkt_path):
            _LOGGER.info('Renew: ticket file %s does not exist', self.tkt_path)
            return

        try:
            ticket_owner = os.path.basename(self.tkt_path)
            subproc.check_call(
                ['kinit', '-R'],
                environ={'KRB5CCNAME': 'FILE:' + self.tkt_path},
                runas=ticket_owner
            )
            _LOGGER.info('Tickets renewed successfully.')
        except subproc.CalledProcessError as err:
            _LOGGER.info('Tickets not renewable, kinit rc: %s',
                         err.returncode)

    @property
    def tkt_path(self):
        """Full path to the ticket file."""
        if self.uid is not None:
            uid = self.uid
        else:
            uid = 'no_ticket'
        return '/tmp/krb5cc_%s' % uid


def krbcc_ok(tkt_path):
    """Check if credential cache is valid (not expired)."""
    try:
        subproc.check_call(['klist', '-5', '-s', tkt_path])
        return True
    except subproc.CalledProcessError:
        _LOGGER.warning('Ticket cache invalid: %s', tkt_path)
        return False


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

    def prune_tickets(self):
        """Remove invalid tickets from directory."""
        published_tickets = self.zkclient.get_children(z.TICKETS)
        for tkt in published_tickets:
            tkt_path = os.path.join(self.tkt_spool_dir, tkt)
            if not krbcc_ok(tkt_path):
                fs.rm_safe(tkt_path)
                zkutils.ensure_deleted(
                    self.zkclient,
                    z.path.tickets(tkt, self.hostname)
                )

    def publish_tickets(self, realms, once=False):
        """Publish list of all tickets present on the locker."""
        zkutils.ensure_exists(self.zkclient, z.TICKETS)
        watcher = dirwatch.DirWatcher(self.tkt_spool_dir)

        def _publish_ticket(tkt_file):
            """Publish ticket details."""
            if tkt_file.startswith('.'):
                return

            if not any([tkt_file.endswith(realm) for realm in realms]):
                _LOGGER.info('Ignore tkt_file: %s', tkt_file)
                return

            try:
                tkt_details = subproc.check_output([
                    'klist', '-5', '-e', '-f', tkt_file
                ])
                tkt_node = z.path.tickets(os.path.basename(tkt_file),
                                          self.hostname)
                zkutils.put(self.zkclient,
                            tkt_node,
                            tkt_details,
                            ephemeral=True)
            except subproc.CalledProcessError:
                _LOGGER.warning('Unable to get tickets details.')

        for tkt_file in glob.glob(os.path.join(self.tkt_spool_dir, '*')):
            _publish_ticket(tkt_file)

        self.prune_tickets()
        last_prune = time.time()

        if once:
            return

        watcher.on_created = _publish_ticket
        while True:
            if time.time() - last_prune > _STALE_TKTS_PRUNE_INTERVAL:
                self.prune_tickets()
                last_prune = time.time()

            if watcher.wait_for_events(timeout=_STALE_TKTS_PRUNE_INTERVAL):
                watcher.process_events(max_events=_DIRWATCH_EVENTS_COUNT)

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
                for princ, encoded in six.iteritems(tkts):
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


def lockers(zkclient):
    """Get registered ticket lockers."""
    endpoints = zkutils.with_retry(zkclient.get_children, z.TICKET_LOCKER)
    random.shuffle(endpoints)
    return endpoints


def request_tickets(zkclient, appname, tkt_spool_dir, principals):
    """Request tickets from the locker for the given app.
    """
    expected = set(principals)
    for locker in lockers(zkclient):
        if not expected:
            _LOGGER.info('Done: all tickets retrieved.')
            return

        host, port = locker.split(':')
        request_tickets_from(host, port, appname, tkt_spool_dir, expected)


def request_tickets_from(host, port, appname, tkt_spool_dir, expected=None):
    """Request tickets from given locker endpoint."""
    service = 'host@%s' % host
    _LOGGER.info('connecting: %s:%s, %s', host, port, service)
    client = gssapiprotocol.GSSAPILineClient(host, int(port), service)
    if expected is None:
        expected = set()
    try:
        if client.connect():
            _LOGGER.debug('connected to: %s:%s, %s', host, port, service)
            client.write(appname.encode())
            _LOGGER.debug('sent: %r', appname)
            while True:
                line = client.read()
                if not line:
                    _LOGGER.debug('Got empty response.')
                    break

                princ, encoded = line.split(b':', 1)
                princ = princ.decode()
                ticket_data = base64.standard_b64decode(encoded)
                if ticket_data:
                    _LOGGER.info('got ticket %s:%s',
                                 princ,
                                 hashlib.sha1(encoded).hexdigest())
                    tkt = Ticket(princ, ticket_data)
                    if store_ticket(tkt, tkt_spool_dir):
                        expected.discard(princ)
                else:
                    _LOGGER.info('got ticket %s:None', princ)
        else:
            _LOGGER.warning('Cannot connect to %s:%s, %s', host, port,
                            service)
    finally:
        client.disconnect()


def store_ticket(tkt, tkt_spool_dir):
    """Store ticket received from ticket locker."""
    _LOGGER.info('store ticket: %s', tkt.princ)
    # Check if locker was able to get all tickets or there are
    # some pending.
    if not tkt.ticket:
        _LOGGER.info('Ticket pending for %r', tkt.princ)
        return False

    _LOGGER.info('Refreshing ticket for %r', tkt.princ)
    if not tkt.write():
        return False

    tkt_spool_path = os.path.join(tkt_spool_dir, tkt.princ)
    tkt.copy(tkt_spool_path)

    # Tickets are stored as fully qualified princ
    # files: foo@krbrealm.
    #
    # For backward compatablity, create "short"
    # ticket link:
    #
    # foo -> foo@krbrealm
    realm_sep = tkt_spool_path.rfind('@')
    tkt_spool_link = tkt_spool_path[:realm_sep]
    if realm_sep != -1:
        # Create relative link without full path.
        _LOGGER.info('Creating link: %s => %s',
                     tkt_spool_link,
                     os.path.basename(tkt_spool_path))
        fs.symlink_safe(tkt_spool_link, os.path.basename(tkt_spool_path))
    return True
