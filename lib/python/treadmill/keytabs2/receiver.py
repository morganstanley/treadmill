"""
receiver class of keytabs2 implementation
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import sqlite3

from treadmill import fs
from treadmill import keytabs2
from treadmill.keytabs2 import kt_split
from treadmill import utils
from treadmill.gssapiprotocol import jsonserver

_LOGGER = logging.getLogger(__name__)


def _ensure_table_exists(database, owner=None):
    """Creates table if table does not exist.

    :param database: Path to SQLite3 db file.
    """
    conn = sqlite3.connect(database)
    cur = conn.cursor()

    # store virtual => proid map
    # keytab: keytab file name e.g. host#vip1.domain.com@realm
    # table columns definitions:
    # proid: matched proid for the VIP keytab
    # vip: vip1.domain.com
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS %s
        (proid text, vip text)
        ''' % keytabs2.TABLE
    )
    conn.commit()
    conn.close()

    if owner is not None:
        (uid, gid) = utils.get_uid_gid(owner)
        os.chown(database, uid, gid)


class KeytabReceiver:
    """Manages keytab exchange.
    """

    __slot__ = ['_kt_spool_dir', '_database', '_owner']

    def __init__(self, kt_spool_dir, database, owner):
        """KeytabReceiver constructor.

        :param kt_spool_dir: Path to store keytab files.
        :param database: Path to SQLite3 db file which stores VIP keytab/proid
                         relationships
        :param owner: Proid of the cell
        """
        self._kt_spool_dir = kt_spool_dir
        self._kt_spool_tmp_dir = '{}.tmp'.format(kt_spool_dir)
        self._database = database
        self._owner = owner
        _ensure_table_exists(database, owner)

    def _check_principal_user(self, princ):
        """Validate keytab principal."""
        if not princ or princ.split('/')[0] != self._owner:
            raise keytabs2.KeytabLockerError(
                'expect user {}, got: {}'.format(self._owner, princ)
            )

    def add(self, _princ, keytabs):
        """Add keytab to locker.
        if client has permission to access a keytab,
        we added it to spool dir after validating the keytabs
        """
        # Use kt-split to validate keytab
        # if validated, return keytab files else return None
        for kt in kt_split.validate_as_file(keytabs, self._kt_spool_tmp_dir):
            dest_kt = os.path.join(self._kt_spool_dir, os.path.basename(kt))
            fs.replace(kt, dest_kt)

    def delete(self, princ, keytabs):
        """Delete keytab to locker.
        Only treadmill owner proid can delete keytab
        """
        self._check_principal_user(princ)
        for kt_name in keytabs:
            fs.rm_safe(os.path.join(self._kt_spool_dir, kt_name))

    def sync(self, princ, desired):
        """Sync proid <=> vip relationship in locker's sqlite
        Only treadmill owner proid can sync relationship of proid/vip
        param desired:
            list of (proid, vip)
        """
        self._check_principal_user(princ)

        conn = sqlite3.connect(self._database)
        cur = conn.cursor()
        try:
            query = 'SELECT proid, vip FROM %s order by vip' % keytabs2.TABLE
            store_virtuals = cur.execute(query).fetchall()
        except sqlite3.OperationalError as err:
            # table may not exist yet, try sync in the next execution
            _LOGGER.warning('wait for keytab locker starting.')
            conn.close()
            return

        (add, modify, delete) = _compare_data(
            store_virtuals,
            sorted(desired, key=lambda v: v[1]),
            1,
        )

        if add:
            sql = 'INSERT INTO %s (proid, vip) VALUES (?, ?)' % keytabs2.TABLE
            try:
                cur.executemany(sql, add)
                conn.commit()
            except sqlite3.OperationalError as err:
                _LOGGER.warning('Failed to add new keytabs in DB: %s', err)

        if delete:
            sql = 'DELETE FROM %s WHERE proid = ? and vip = ?' % keytabs2.TABLE
            try:
                cur.executemany(sql, delete)
                conn.commit()
            except sqlite3.OperationalError as err:
                _LOGGER.warning('Failed to delete extra keytabs from DB: %s',
                                err)

        if modify:
            sql = 'UPDATE %s set proid = ? where vip = ?' % keytabs2.TABLE
            try:
                cur.executemany(sql, modify)
                conn.commit()
            except sqlite3.OperationalError as err:
                _LOGGER.warning('Failed to modify keytabs in DB: %s', err)


def _compare_data(stored, desired, idx=0):
    """Calculate the virtual to be added, modified, deleted
    """
    add = []
    modify = []
    delete = []
    current = 0
    total_stored = len(stored)

    for virtual in desired:
        while current < total_stored and virtual[idx] > stored[current][idx]:
            delete.append(stored[current])
            current += 1

        if current >= total_stored:
            add.append(virtual)
            continue

        if virtual[idx] == stored[current][idx]:
            if virtual != stored[current]:
                modify.append(virtual)

            current += 1
            continue

        add.append(virtual)

    # add unprocessed stored elements to delete
    while current < total_stored:
        delete.append(stored[current])
        current += 1

    return (add, modify, delete)


def get_receiver_server(receiver, port):
    """Build keytab server protocol.
    """
    from twisted.internet import protocol
    from twisted.internet import reactor

    def _response(success=False, message=None, keytabs=None):
        """Construct response."""
        return {
            'success': success,
            'message': message,
            'keytabs': keytabs,
        }

    class _KeytabReceiverServerProtocol(jsonserver.GSSAPIJsonServer):
        """Implement keytab receiver server protocol."""

        def _put(self, req):
            """Store encoded keytab.
            """
            try:
                keytabs = req['keytabs']
            except KeyError:
                raise keytabs2.KeytabLockerError('No "keytabs" in request')

            _LOGGER.debug('put keytabs: %s', keytabs)
            receiver.add(self.peer(), keytabs)

            return _response(success=True)

        def _sync(self, req):
            """sync proid keytab relationship
            """
            try:
                mapping = req['mapping']
            except KeyError:
                raise keytabs2.KeytabLockerError('No "mapping" in request')

            # we convert into a tuple list
            mapping = [(item[0], item[1]) for item in mapping]

            _LOGGER.debug('sync mapping: %r', mapping)
            receiver.sync(self.peer(), mapping)

            return _response(success=True)

        def on_request(self, request):
            """Process keytab requests."""
            action = request.get('action')
            try:
                if action == 'put':
                    return self._put(request)
                elif action == 'sync':
                    return self._sync(request)
                else:
                    return _response(success=False, message='Unknown Action')

            except keytabs2.KeytabLockerError as err:
                return _response(success=False, message=err.message)

    class _KeytabReceiverServer:
        """Keytab receiver server."""

        def __init__(self):
            """_KeytabLockerServer constructor."""
            factory = protocol.Factory.forProtocol(
                _KeytabReceiverServerProtocol
            )
            listening_port = reactor.listenTCP(port, factory)

            def _get_actual_port():
                """Get actual listening port."""
                return listening_port.getHost().port

            def _run():
                """Start keytab locker server"""
                reactor.run()

            self.get_actual_port = _get_actual_port
            self.run = _run

    return _KeytabReceiverServer()
