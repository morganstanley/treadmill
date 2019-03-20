"""
Handles keytab forwarding from keytab locker to the node. This is a upgraded
version from `treadmill.keytab` which supports requesting by SPNs and relevant
ownership.
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
import re
import sqlite3

from treadmill import discovery
from treadmill import exc
from treadmill import fs
from treadmill import sysinfo


_LOGGER = logging.getLogger(__name__)

# sqlite3 table name for tracking relationships between VIP keytab and proid
_TABLE = 'keytab_proid_relations'


class _KeytabLockerError(exc.TreadmillError):
    """Treadmill keytab locker operation error.
    """

    __slots__ = ()


def _write_keytab(fname, data):
    """Safely writes data to file.

    :param fname: Keytab filename.
    :param data: Keytab data in bytes.
    """
    _LOGGER.info('Writing %s: %s', fname,
                 hashlib.sha1(data).hexdigest())
    fs.write_safe(
        fname,
        lambda f: f.write(data),
        prefix='.tmp',
        mode='wb'
    )


def _keytab2hostname(keytab):
    """Parse hostname from keytab file name."""
    res = re.match('^host#(.+)@(.*)$', keytab)
    if res:
        return res.group(1)
    return None


def ensure_table_exists(database):
    """Creates table if table does not exist.

    :param database: Path to SQLite3 db file.
    """
    conn = sqlite3.connect(database)
    cur = conn.cursor()

    # table columns definitions:
    # proid: matched proid for the VIP keytab
    # keytab: keytab file name e.g. host#vip1.domain.com@realm
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS %s (proid text, keytab text)
        ''' % _TABLE
    )
    conn.commit()
    conn.close()


class KeytabLocker:
    """Manages keytab exchange.
    """

    def __init__(self, kt_spool_dir, database):
        """KeytabLocker constructor.

        :param kt_spool_dir: Path to store keytab files.
        :param database: Path to SQLite3 db file which stores VIP keytab/proid
                         relationships
        """
        self.kt_spool_dir = kt_spool_dir
        self.database = database

    def _get(self, vips):
        """Get vip host keytabs"""
        keytabs = dict()
        try:
            for kt_file in glob.glob(os.path.join(self.kt_spool_dir, '*')):
                if kt_file.startswith('.tmp'):
                    continue

                vip = _keytab2hostname(kt_file)
                if vip and vip in vips:
                    with io.open(kt_file, 'rb') as f:
                        keytabs[os.path.basename(kt_file)] = f.read()

        except EnvironmentError:
            _LOGGER.exception('Unhandled exception reading: %s',
                              self.kt_spool_dir)

        return keytabs

    def _check_principal(self, princ):
        """Validate keytab principal."""
        if not princ or not princ.startswith('host/'):
            raise _KeytabLockerError('expect host principal, got: %r' % princ)

    def _check_vip_keytabs(self, proid, vips):
        """Validate if proid matchs all required vip keytabs."""
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        sql = 'SELECT keytab FROM relations where proid = "%s"' % proid
        saved = set(row[0] for row in cur.execute(sql))
        conn.close()

        expected = set(vips)
        missed = expected - saved
        _LOGGER.debug('Expected: %r', sorted(expected))
        _LOGGER.debug('Actual  : %r', sorted(saved))

        if missed:
            raise _KeytabLockerError('miss vip keytabs: %r' % missed)

    def get(self, princ, proid, vips):
        """Process vip keytabs request."""
        _LOGGER.info('Processing request %s, %s, %r', princ, proid, vips)

        self._check_principal(princ)
        self._check_vip_keytabs(proid, vips)

        result = self._get(vips)
        return result


def get_listening_server(locker, port):
    """Build keytab server protocol.
    """
    from treadmill.gssapiprotocol import jsonserver
    from twisted.internet import protocol
    from twisted.internet import reactor

    def _response(success=False, message=None, keytabs=None):
        """Construct response."""
        return {
            'success': success,
            'message': message,
            'keytabs': keytabs,
        }

    class _KeytabLockerServerProtocol(jsonserver.GSSAPIJsonServer):
        """Implement keytab locker server protocol."""

        def _get(self, req):
            """Get keytabs for given host/app.
            """
            try:
                keytabs = locker.get(self.peer(), req['proid'], req['vips'])
            except KeyError:
                raise _KeytabLockerError('Miss "proid" or "vips"')

            _LOGGER.info('Sending keytabs for: %r', keytabs.keys())

            # encode keytab binary data for json protocol compatibility
            keytabs = {
                ktname: base64.urlsafe_b64encode(binary)
                for ktname, binary in keytabs.items()
            }
            return _response(success=True, keytabs=keytabs)

        def _put(self, req):
            """Store encoded keytab.
            """
            try:
                keytab, encoded = req['keytab'], req['encoded']
            except KeyError:
                raise _KeytabLockerError('Miss "keytab" or "encoded"')

            _LOGGER.info('put %s - %s',
                         keytab,
                         hashlib.sha1(encoded).hexdigest())

            _write_keytab(
                os.path.join(locker.kt_spool_dir, keytab),
                encoded
            )
            return _response(success=True)

        def on_request(self, request):
            """Process keytab requests."""
            action = request.get('action')
            try:
                if action == 'get':
                    return self._get(request)
                elif action == 'put':
                    return self._put(request)
                else:
                    return _response(success=False, message='Unknown Action')

            except _KeytabLockerError as err:
                return _response(success=False, message=err.message)

    class _KeytabLockerServer:
        """Keytab locker server."""

        def __init__(self):
            """_KeytabLockerServer constructor."""
            factory = protocol.Factory.forProtocol(_KeytabLockerServerProtocol)
            listening_port = reactor.listenTCP(port, factory)

            def _get_actual_port():
                """Get actual listening port."""
                return listening_port.getHost().port

            def _run():
                """Start keytab locker server"""
                reactor.run()

            self.get_actual_port = _get_actual_port
            self.run = _run

    return _KeytabLockerServer()


def _get_keytabs_from(host, port, proid, vips, spool_dir):
    """Get VIP keytabs from keytab locker server.
    """
    from treadmill.gssapiprotocol import jsonclient

    service = 'host@%s' % host
    _LOGGER.info('connecting: %s:%s, %s', host, port, service)
    client = jsonclient.GSSAPIJsonClient(host, int(port), service)

    try:
        if not client.connect():
            _LOGGER.warning(
                'Cannot connect to %s:%s, %s', host, port, service
            )
            return False

        _LOGGER.debug('connected to: %s:%s, %s', host, port, service)

        request = {
            'action': 'get',
            'proid': proid,
            'vips': vips,
        }
        client.write_json(request)

        res = client.read_json()
        if '_error' in res:
            _LOGGER.warning('keytab locker internal err: %s', res['_error'])
            return False

        if not res['success']:
            _LOGGER.warning('get keytab err: %s', res['message'])
            return False

        for ktname, encoded in res['keytabs'].items():
            if encoded:
                _LOGGER.info('got keytab %s:%r',
                             ktname,
                             hashlib.sha1(encoded).hexdigest())
                keytab_data = base64.urlsafe_b64decode(encoded)
                kt_file = os.path.join(spool_dir, ktname)
                _write_keytab(kt_file, keytab_data)
            else:
                _LOGGER.warning('got empty keytab %s', ktname)
                return False

        return True

    finally:
        client.disconnect()


def request_keytabs(zkclient, proid, vips, spool_dir):
    """Request VIP keytabs from the keytab locker.

    :param zkclient: Existing zk connection.
    :param proid: Proid in container appname.
    :param vips: VIP host list defined in manifest.
    :param spool_dir: Path to keep keytabs fetched from keytab locker.
    """
    pattern = "{0}.keytabs-v2".format(os.environ['TREADMILL_ID'])
    iterator = discovery.iterator(zkclient, pattern, 'keytabs', False)
    hostports = []

    for (_app, hostport) in iterator:
        if not hostport:
            continue
        host, port = hostport.split(':')
        hostports.append((host, int(port)))

    random.shuffle(hostports)

    for (host, port) in hostports:
        fs.mkdir_safe(spool_dir)
        if _get_keytabs_from(host, port, proid, vips, spool_dir):
            return True

    return False


def sync_relations(spool_dir, database, query_proid_func):
    """Sync VIP host keytab/proid relation if it does not exist.

    :param spool_dir:
        Path to keep keytabs fetched from keytab locker.
    :param database:
        Path to SQLite3 db file which stores VIP keytab/proid relationships.
    :param query_proid_func:
        Function object with signature `func(ktname: str) -> str`.
    """
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    try:
        keytab2proid = dict(
            cur.execute('SELECT keytab, proid FROM %s ' % _TABLE)
        )
    except sqlite3.OperationalError as err:
        # table may not exist yet, try sync in the next execution
        _LOGGER.warning('wait for keytab locker starting.')
        conn.close()
        return

    hostname = sysinfo.hostname()

    missed = set()
    for ktname in glob.glob(os.path.join(spool_dir, '*')):
        ktname = os.path.basename(ktname)
        # ignore local host keytab
        if ktname not in keytab2proid and _keytab2hostname(ktname) != hostname:
            missed.add(ktname)

    _LOGGER.debug('keytabs without proid: %r', sorted(missed))

    if missed:
        values = []
        for ktname in missed:
            proid = query_proid_func(ktname)
            _LOGGER.debug('keytab %s matches proid %s', ktname, proid)
            values.append((ktname, proid))

        cur.executemany(
            """
            INSERT INTO %s (keytab, proid) VALUES (?, ?)
            """ % _TABLE,
            values,
        )
        conn.commit()

    conn.close()
