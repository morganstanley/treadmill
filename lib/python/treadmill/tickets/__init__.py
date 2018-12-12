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
import stat  # pylint: disable=wrong-import-order
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


class Ticket:
    """Helper class to manage krb ticket.

    princ - fully qualified kerberos principal uid@realm.
    ticket - base64 encoded ticket.
    """

    def __init__(self, princ, ticket):
        self.princ = princ
        self.ticket = ticket
        self.user = princ[:princ.find('@') if '@' in princ else len(princ)]
        try:
            self.uid = utils.get_uid_gid(self.user)[0]
        except KeyError:
            _LOGGER.warning('princ/user does not exist: %s', self.user)
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
            subproc.check_call(
                ['kinit', '-R'],
                environ={
                    'KRB5CCNAME': 'FILE:' + self.tkt_path,
                },
                runas=self.user
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


def lockers(zkclient):
    """Get registered ticket lockers."""
    endpoints = zkutils.with_retry(
        zkclient.get_children, z.path.ticket_locker()
    )
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

    tkt.renew()
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
