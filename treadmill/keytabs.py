"""Handles keytab forwarding from keytab locker to the node.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import base64
import glob
import hashlib
import io
import logging
import os
import random
import shutil
import tempfile

from twisted.internet import reactor
from twisted.internet import protocol

from treadmill import fs
from treadmill import gssapiprotocol
from treadmill import subproc
from treadmill import sysinfo
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils

_LOGGER = logging.getLogger(__name__)


def _write(fname, data):
    """Safely writes data to file."""
    # TODO: move to treadmill.utils?
    _LOGGER.info('Writing %s: %s', fname,
                 hashlib.sha1(data).hexdigest())

    fs.write_safe(
        fname,
        lambda f: f.write(data),
        prefix='.tmp'
    )


class KeytabLocker(object):
    """Manages keytab exchange."""

    def __init__(self, zkclient, kt_spool_dir):
        self.zkclient = zkclient
        self.kt_spool_dir = kt_spool_dir
        self.zkclient.add_listener(zkutils.exit_on_lost)

    def register_endpoint(self, port):
        """Register ticket locker endpoint in Zookeeper."""
        hostname = sysinfo.hostname()
        self.zkclient.ensure_path(z.KEYTAB_LOCKER)

        node_path = z.path.keytab_locker('%s:%s' % (hostname, port))
        _LOGGER.info('registering locker: %s', node_path)
        if self.zkclient.exists(node_path):
            _LOGGER.info('removing previous node %s', node_path)
            zkutils.ensure_deleted(self.zkclient, node_path)

        zkutils.put(self.zkclient, node_path, {}, acl=None, ephemeral=True)

    def close_zk_connection(self):
        """Close Zookeepeer connection."""
        self.zkclient.remove_listener(zkutils.exit_on_lost)
        zkutils.disconnect(self.zkclient)

    def get(self, princ):
        """Process keytab request."""

        _LOGGER.info('Processing request from: %s', princ)
        keytabs = dict()
        if not princ or not princ.startswith('host/'):
            _LOGGER.error('Host principal expected, got: %s.', princ)
            return {}

        hostname = princ[len('host/'):princ.rfind('@')]

        # Check the the server is valid server in the cell.
        if not self.zkclient.exists(z.path.server(hostname)):
            _LOGGER.error('Invalid server: %s', hostname)
            return {}

        try:
            for kt_file in glob.glob(os.path.join(self.kt_spool_dir, '*')):
                if kt_file.startswith('.tmp'):
                    continue

                with io.open(kt_file) as f:
                    keytabs[os.path.basename(kt_file)] = f.read()
        except EnvironmentError:
            _LOGGER.exception('Unhandled exception reading: %s',
                              self.kt_spool_dir)

        return keytabs


def run_server(locker):
    """Runs tickets server."""
    _LOGGER.info('Keytab locker server starting.')

    # no __init__ method.
    #
    # pylint: disable=W0232
    class KeytabLockerServer(gssapiprotocol.GSSAPILineServer):
        """Keytab locker server."""

        def _get(self):
            """Get keytabs for given host/app."""
            keytabs = locker.get(self.peer())
            _LOGGER.info('Sending keytabs for: %r', keytabs.keys())
            for kt_name, encoded in keytabs.iteritems():
                _LOGGER.info('Sending keytab: %s:%s',
                             kt_name,
                             hashlib.sha1(encoded).hexdigest())
                self.write('%s:%s' % (kt_name, encoded))

        def _put(self, kt_name, encoded):
            """Store encoded keytab."""
            _LOGGER.info('put %s - %s',
                         kt_name,
                         hashlib.sha1(encoded).hexdigest())
            _write(os.path.join(locker.kt_spool_dir, kt_name), encoded)

        @utils.exit_on_unhandled
        def got_line(self, line):
            """Callback on received line."""
            items = line.split()
            action = items[0]

            if action == 'get':
                self._get()
            elif action == 'put':
                self._put(kt_name=items[1], encoded=items[2])

            self.write('')

    class KeytabLockerServerFactory(protocol.Factory):
        """KeytabLockerServer factory."""

        def buildProtocol(self, addr):  # pylint: disable=C0103
            return KeytabLockerServer()

    port = reactor.listenTCP(0, KeytabLockerServerFactory()).getHost().port
    locker.register_endpoint(port)
    reactor.run()


def _get_keytabs_from(host, port, spool_dir):
    """Get keytabs from keytab locker server."""
    service = 'host@%s' % host
    _LOGGER.info('connecting: %s:%s, %s', host, port, service)
    client = gssapiprotocol.GSSAPILineClient(host, int(port), service)

    try:
        if not client.connect():
            _LOGGER.warning(
                'Cannot connect to %s:%s, %s', host, port, service
            )
            return False

        _LOGGER.debug('connected to: %s:%s, %s', host, port, service)

        client.write('get')
        while True:
            line = client.read()
            if not line:
                _LOGGER.debug('End of response.')
                break

            ktname, encoded = line.split(':')
            if encoded:
                _LOGGER.info('got keytab %s:%s',
                             ktname,
                             hashlib.sha1(encoded).hexdigest())
                keytab = base64.urlsafe_b64decode(encoded)
                _write(os.path.join(spool_dir, ktname), keytab)
            else:
                _LOGGER.warning('got empty keytab %s', ktname)

        return True

    finally:
        client.disconnect()


def make_keytab(zkclient, spool_dir, host_kt=None):
    """Request keytabs from the locker."""
    lockers = zkutils.with_retry(zkclient.get_children, z.KEYTAB_LOCKER)
    random.shuffle(lockers)

    for locker in lockers:
        host, port = locker.split(':')

        try:
            tmp_dir = tempfile.mkdtemp()
            if _get_keytabs_from(host, port, tmp_dir):
                inputs = glob.glob(os.path.join(tmp_dir, '*'))
                if host_kt:
                    inputs.append(host_kt)

                kt_file = os.path.join(spool_dir, 'krb5.keytab')
                kt_temp = os.path.join(tmp_dir, 'krb5.keytab')
                subproc.check_call(['kt-add', kt_temp] + inputs)
                os.rename(kt_temp, kt_file)
                break

        finally:
            shutil.rmtree(tmp_dir)
