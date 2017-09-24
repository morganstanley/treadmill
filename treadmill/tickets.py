"""Handles ticket forwarding from the ticket master to the node.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import base64
import hashlib
import io
import logging
import os
import pwd
import random
import shutil
import stat
import tempfile

import kazoo
import kazoo.client

from twisted.internet import reactor
from twisted.internet import protocol

import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import fs
from treadmill import gssapiprotocol
from treadmill import subproc
from treadmill import sysinfo
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils

_LOGGER = logging.getLogger(__name__)


class Ticket(object):
    """Helper class to manage krb ticket.

    princ - fully qualified kerberos principal uid@realm.
    ticket - base64 encoded ticket.
    """

    def __init__(self, princ, ticket):
        self.princ = princ
        self.ticket = ticket
        user, _realm = princ.split('@')
        try:
            self.uid = pwd.getpwnam(user).pw_uid
        except KeyError:
            _LOGGER.warning('princ/user does not exist: %s', user)
            self.uid = None

    def __repr__(self):
        ticket_cs = None
        if self.ticket:
            ticket_cs = hashlib.sha1(self.ticket).hexdigest()
        return "Ticket(princ=%s, ticket=%s)" % (self.princ, ticket_cs)

    def __unicode__(self):
        """Returns printable info about the ticket"""
        if self.ticket:
            return "Ticket: %s, %s" % (self.princ,
                                       hashlib.sha1(self.ticket).hexdigest())
        else:
            return "Ticket: %s, null"

    def __eq__(self, other):
        return self.princ == other.princ and self.ticket == other.ticket

    def write(self, path=None):
        """Writes the ticket to /var/spool/ticket/<princ>."""
        def _write_temp(tkt_file):
            # Write the file
            tkt_file.write(self.ticket)
            # Set the owner
            if self.uid is not None:
                os.fchown(tkt_file.fileno(), self.uid, -1)
            # TODO: Should we enforce the mode too?
            tkt_file.flush()

        if path is None:
            path = self.tkt_path
        try:
            fs.write_safe(
                path,
                _write_temp,
                prefix='.tmp' + self.princ
            )
        except (IOError, OSError):
            _LOGGER.exception('Error writing ticket file: %s', path)

    def copy(self, dst, src=None):
        """Atomically copy tickets to destination."""
        if src is None:
            src = self.tkt_path

        dst_dir = os.path.dirname(dst)
        try:
            with io.open(src, 'rb') as tkt_src_file:
                with tempfile.NamedTemporaryFile(dir=dst_dir,
                                                 prefix='.tmp' + self.princ,
                                                 delete=False,
                                                 mode='w') as tkt_dst_file:
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
            _LOGGER.exception('Error copying ticket from %s to %s', src, dst)
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
        except subprocess.CalledProcessError as err:
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
    except subprocess.CalledProcessError:
        _LOGGER.warning('Ticket cache invalid: %s', tkt_path)
        return False


class TicketLocker(object):
    """Manages ticket exchange between ticket locker and the container."""

    def __init__(self, zkclient, tkt_spool_dir):
        self.zkclient = zkclient
        self.tkt_spool_dir = tkt_spool_dir
        self.zkclient.add_listener(zkutils.exit_on_lost)

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
            return

        hostname = princ[len('host/'):princ.rfind('@')]

        if not self.zkclient.exists(z.path.placement(hostname, appname)):
            _LOGGER.error('App %s not scheduled on node %s', appname, hostname)
            return

        tkt_dict = dict()
        try:
            appnode = z.path.scheduled(appname)
            app = zkutils.with_retry(zkutils.get, self.zkclient, appnode)

            tickets = set(app.get('tickets', []))
            _LOGGER.info('App tickets: %s: %r', appname, tickets)
            for ticket in tickets:
                tkt_file = os.path.join(self.tkt_spool_dir, ticket)
                if os.path.exists(tkt_file):
                    with io.open(tkt_file, 'rb') as f:
                        encoded = base64.urlsafe_b64encode(f.read())
                        tkt_dict[ticket] = encoded
                else:
                    _LOGGER.warning(
                        'Ticket file does not exist: %s', tkt_file
                    )

        except kazoo.client.NoNodeError:
            _LOGGER.info('App does not exist: %s', appname)

        return tkt_dict


# Disable warning for too many branches.
# pylint: disable=R0912
def run_server(locker):
    """Runs tickets server."""
    _LOGGER.info('Tickets server starting.')

    # no __init__ method.
    #
    # pylint: disable=W0232
    class TicketLockerServer(gssapiprotocol.GSSAPILineServer):
        """Ticket locker server."""

        @utils.exit_on_unhandled
        def got_line(self, line):
            """Callback on received line."""
            appname = line
            tkts = locker.process_request(self.peer(), appname)
            if tkts:
                _LOGGER.info('Sending tickets for: %r', tkts.keys())
                for princ, encoded in tkts.items():
                    if encoded:
                        _LOGGER.info('Sending ticket: %s:%s',
                                     princ,
                                     hashlib.sha1(encoded).hexdigest())
                        self.write('%s:%s' % (princ, encoded))
                    else:
                        _LOGGER.info('Sending ticket %s, None', princ)
                        self.write('%s:' % princ)
            else:
                _LOGGER.info('No tickets found for app: %s', appname)

            self.write('')

    class TicketLockerServerFactory(protocol.Factory):
        """TicketLockerServer factory."""

        def buildProtocol(self, addr):  # pylint: disable=C0103
            return TicketLockerServer()

    port = reactor.listenTCP(0, TicketLockerServerFactory()).getHost().port
    locker.register_endpoint(port)
    reactor.run()


def request_tickets(zkclient, appname):
    """Request tickets from the locker for the given app.
    """
    # Too many nested blocks.
    #
    # pylint: disable=R0101
    lockers = zkutils.with_retry(zkclient.get_children,
                                 z.TICKET_LOCKER)
    random.shuffle(lockers)
    tickets = []
    for locker in lockers:
        host, port = locker.split(':')
        service = 'host@%s' % host
        _LOGGER.info('connecting: %s:%s, %s', host, port, service)
        client = gssapiprotocol.GSSAPILineClient(host, int(port), service)
        try:
            if client.connect():
                _LOGGER.debug('connected to: %s:%s, %s', host, port, service)
                client.write(appname)
                _LOGGER.debug('sent: %s', appname)
                while True:
                    line = client.read()
                    if not line:
                        _LOGGER.debug('Got empty response.')
                        break

                    princ, encoded = line.split(b':')
                    if encoded:
                        _LOGGER.info(
                            'got ticket %s:%s',
                            princ,
                            hashlib.sha1(encoded.encode()).hexdigest()
                        )
                        ticket = Ticket(princ,
                                        base64.urlsafe_b64decode(encoded))
                        tickets.append(ticket)
                    else:
                        _LOGGER.info('got ticket %s:None', princ)
                        tickets.append(Ticket(princ, None))
                break
            else:
                _LOGGER.warning('Cannot connect to %s:%s, %s', host, port,
                                service)
        except Exception:
            _LOGGER.exception('Exception processing tickets.')
            raise

        finally:
            client.disconnect()

    return tickets


def store_tickets(reply, tkt_spool_dir):
    """Store tickets received from ticket locker."""
    _LOGGER.info('got tickets: %s', reply)
    # Check if locker was able to get all tickets or there are
    # some pending.
    for tkt in reply:
        if not tkt.ticket:
            _LOGGER.info('Ticket pending for %r', tkt.princ)
            continue

        _LOGGER.info('Refreshing ticket for %r', tkt.princ)
        tkt.write()
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
