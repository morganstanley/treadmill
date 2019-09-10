"""
locker class of keytabs2 implementation
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import logging
import os
import re
import socket
import sqlite3

import kazoo
import kazoo.client

from treadmill import keytabs2
from treadmill import zknamespace as z
from treadmill import zkutils
from treadmill.gssapiprotocol import jsonserver

_LOGGER = logging.getLogger(__name__)

_KEYTAB_PATTERN = r'\w+#(.+)@.+'
_KEYTAB_RE_OBJ = re.compile(_KEYTAB_PATTERN)


def _translate_vip(keytab):
    """Get ip address from hostname inside keytab string
    """
    match = _KEYTAB_RE_OBJ.match(keytab)
    if match:
        hostname = match.group(1)
    else:
        raise keytabs2.KeytabLockerError(
            'Keytab {} in wrong format'.format(keytab)
        )

    _LOGGER.debug('Trying to get vip of %s', hostname)
    ipaddress = socket.gethostbyname(hostname)
    _LOGGER.info('keytab => vip: %s => %s', keytab, ipaddress)
    return ipaddress


class KeytabLocker:
    """Keytab Locker to provide keytabs to requesting apps
    """

    def __init__(self, kt_spool_dir, database, zkclient):
        """KeytabLocker constructor.

        :param kt_spool_dir: Path to store keytab files.
        :param database: Path to SQLite3 db file which stores VIP keytab/proid
                         relationships
        """
        self.zkclient = zkclient
        self.zkclient.add_listener(zkutils.exit_on_lost)
        self._kt_spool_dir = kt_spool_dir
        self._database = database

    def fetch(self, princ, addresses):
        """fetch keytabs of the address from locker
        returns:
            list -- encoded keytab contents belonging to addresses
        """
        if not princ or not princ.startswith('host/'):
            raise keytabs2.KeytabLockerError(
                'princ "{}" not accepted'.format(princ)
            )

        hostname = princ[len('host/'):princ.rfind('@')]
        if not self.zkclient.exists(z.path.server(hostname)):
            _LOGGER.error('Invalid server: %s', hostname)
            return {}

        try:
            for hostname in addresses:
                keytab_files = glob.glob(
                    os.path.join(self._kt_spool_dir, '*#{}@*'.format(hostname))
                )
                kts = {
                    os.path.basename(keytab_file): keytabs2.read_keytab(
                        keytab_file
                    )
                    for keytab_file in keytab_files
                }
        except OSError as err:
            raise keytabs2.KeytabLockerError(err)

        return kts

    def get(self, princ, app_name):
        """Get keytabs defined in manifest from locker.
        returns:
            list -- encoded keytab contents required by app
        """
        keytab_names = self.query(princ, app_name)

        try:
            keytabs = {
                keytab: keytabs2.read_keytab(
                    os.path.join(self._kt_spool_dir, keytab)
                )
                for keytab in keytab_names
            }
        except OSError as err:
            raise keytabs2.KeytabLockerError(err)

        return keytabs

    def query(self, princ, app_name):
        """query if keytabs are valid in manifest
        returns:
            list -- keytab names required by app
        """
        vips = self._query_proid_vips(app_name)
        keytabs = self._get_app_keytabs(princ, app_name)

        for keytab in keytabs:
            vip = _translate_vip(keytab)

            if vip not in vips:
                raise keytabs2.KeytabLockerError(
                    '{} of keytab {} does not exist or of wrong proid'.format(
                        vip, keytab)
                )
        return keytabs

    def _query_proid_vips(self, appname):
        """query proid vips relationship
        """
        proid = appname.split('.')[0]

        res = set()
        if not os.path.exists(self._database):
            _LOGGER.error('DB %s not exist', self._database)
            raise keytabs2.KeytabLockerError('DB not exist')

        conn = sqlite3.connect(self._database)
        cur = conn.cursor()
        try:
            query = 'SELECT vip FROM {} where proid = ?'.format(keytabs2.TABLE)
            store_virtuals = cur.execute(query, (proid,)).fetchall()
            res = set([virtual[0] for virtual in store_virtuals])
        except sqlite3.OperationalError as err:
            # table may not exist yet, try sync in the next execution
            _LOGGER.warning('wait for keytab locker starting.')
        finally:
            conn.close()
        return res

    def _get_app_keytabs(self, princ, appname):
        """Get keytabs required for the given app."""
        # TODO: the logic is duplicated with ticket locker
        # we need to refactor to implement generic locker in the future
        if not princ or not princ.startswith('host/'):
            raise keytabs2.KeytabLockerError(
                'princ "{}" not accepted'.format(princ)
            )

        hostname = princ[len('host/'):princ.rfind('@')]

        if not self.zkclient.exists(z.path.placement(hostname, appname)):
            _LOGGER.error('App %s not scheduled on node %s', appname, hostname)
            return []

        try:
            appnode = z.path.scheduled(appname)
            app = zkutils.with_retry(zkutils.get, self.zkclient, appnode)

            return app.get('keytabs', [])
        except kazoo.client.NoNodeError:
            _LOGGER.info('App does not exist: %s', appname)
            return []


def get_locker_server(locker, port):
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

    class _KeytabLockerServerProtocol(jsonserver.GSSAPIJsonServer):
        """Implement keytab receiver server protocol."""

        def _get(self, req):
            """get keytabs from appname
            """
            if 'app' in req:
                app_name = req['app']
                kts = locker.get(self.peer(), app_name)
            elif 'addresses' in req:
                addresses = req['addresses']
                kts = locker.fetch(self.peer(), addresses)
            else:
                raise keytabs2.KeytabLockerError(
                    '"app" or "addresses" must be in request'
                )
            return _response(success=True, keytabs=kts)

        def _query(self, req):
            """query keytabs from appname
            """
            try:
                app_name = req['app']
            except KeyError:
                raise keytabs2.KeytabLockerError('No "app" in request')

            locker.query(self.peer(), app_name)
            return _response(success=True)

        def on_request(self, request):
            """Process keytab requests."""
            action = request.get('action')
            try:
                if action == 'get':
                    return self._get(request)
                elif action == 'query':
                    return self._query(request)
                else:
                    return _response(success=False, message='Unknown Action')

            except keytabs2.KeytabLockerError as err:
                _LOGGER.error(err.message)
                return _response(success=False, message=err.message)

    class _KeytabLockerServer:
        """Keytab receiver server."""

        def __init__(self):
            """_KeytabLockerServer constructor."""
            factory = protocol.Factory.forProtocol(
                _KeytabLockerServerProtocol
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

    return _KeytabLockerServer()
