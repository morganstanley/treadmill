"""Treadmill context."""

import importlib
import logging

import ldap3

from treadmill import admin
from treadmill import zkutils
from treadmill import dnsutils


_LOGGER = logging.getLogger(__name__)


class ContextError(Exception):
    """Raised when unable to connect to LDAP or Zookeeper."""
    pass


class AdminContext(object):
    """Ldap context."""
    __slots__ = (
        'search_base',
        '_url',
        '_conn',
        '_resolve',
    )

    def __init__(self, resolve=None):
        self.search_base = None
        self._url = None
        self._conn = None
        self._resolve = resolve

    @property
    def url(self):
        """URL, getter"""
        return self._url

    @url.setter
    def url(self, value):
        """Set URL, then nullify the connection"""
        self._url = value
        self._conn = None

    @property
    def conn(self):
        """Lazily establishes connection to admin LDAP."""
        if self._conn is None:
            if self.search_base is None:
                raise ContextError('LDAP search base not set.')

            if self.url is None:
                if self._resolve:
                    self._resolve()
                if self.url is None:
                    raise ContextError('LDAP url not set.')

            _LOGGER.debug('Connecting to LDAP %s, %s',
                          self.url, self.search_base)

            self._conn = admin.Admin(self.url, self.search_base)
            self._conn.connect()

        return self._conn


class ZkContext(object):
    """Zookeeper context."""
    __slots__ = (
        'url',
        'proid',
        '_conn',
        '_resolve',
    )

    def __init__(self, resolve=None):
        self.url = None
        self.proid = None
        self._conn = None
        self._resolve = resolve

    @property
    def conn(self):
        """Lazily creates Zookeeper client."""
        if self._conn is None:
            _LOGGER.debug('Connecting to Zookeeper %s', self.url)
            if self.url is None:
                if self._resolve:
                    self._resolve()
                if self.url is None:
                    raise ContextError('Zookeeper url not set.')

            self.proid, _ = self.url[len('zookeeper://'):].split('@')
            self._conn = zkutils.connect(self.url, listener=zkutils.exit_never)

        return self._conn


class Context(object):
    """Global connection context."""
    __slots__ = (
        'cell',
        'ldap',
        'zk',
        'dns_domain',
        'admin_api_scope',
        'ctx_plugin',
        'resolvers',
    )

    def __init__(self):
        self.cell = None
        self.dns_domain = None
        self.ldap = AdminContext(self.resolve)
        self.zk = ZkContext(self.resolve)
        self.admin_api_scope = (None, None)
        self.ctx_plugin = None

        try:
            self.ctx_plugin = importlib.import_module(
                'treadmill.plugins.context')
            self.dns_domain = self.ctx_plugin.dns_domain()
            self.admin_api_scope = self.ctx_plugin.api_scope()
            self.ldap.search_base = self.ctx_plugin.ldap_search_base()
        except Exception as err:  # pylint: disable=W0703
            _LOGGER.debug('Unable to load context plugin: %s.', err)

        self.resolvers = [
            lambda _: self.zk.url,
            self._resolve_cell_from_dns,
            self._resolve_cell_from_ldap,
        ]

    def scopes(self):
        """Returns supported scopes."""
        scopes = ['cell']
        if self.ctx_plugin:
            scopes.extend(self.ctx_plugin.scopes())

        return scopes

    def _resolve_srv(self, srv_rec):
        """Returns list of host, port tuples for given srv record."""
        _LOGGER.debug('Query DNS -t SRV %s.%s', srv_rec, self.dns_domain)
        if not self.dns_domain:
            raise ContextError('Treadmill DNS domain not specified.')

        result = dnsutils.srv(srv_rec + '.' + self.dns_domain)
        _LOGGER.debug('Result: %r', result)

        if result:
            return [dnsutils.srv_target_to_url(srv_rec, target)
                    for target in result]
        else:
            raise ContextError('No srv records found: %s' % srv_rec)

    def cell_api(self, restapi=None):
        """Resolve REST API endpoints."""
        if restapi:
            return [restapi]

        if not self.cell:
            raise ContextError('Cell is not specified.')

        return self._resolve_srv('_http._tcp.cellapi.' + self.cell + '.cell')

    def state_api(self, restapi=None):
        """Resolve state API endpoints."""
        if restapi:
            return [restapi]

        if not self.cell:
            raise ContextError('Cell is not specified.')

        return self._resolve_srv('_http._tcp.stateapi.' + self.cell + '.cell')

    def ws_api(self, wsapi=None):
        """Resolve state API endpoints."""
        if wsapi:
            return [wsapi]

        if not self.cell:
            raise ContextError('Cell is not specified.')

        return self._resolve_srv('_ws._tcp.wsapi.' + self.cell + '.cell')

    def admin_api(self, restapi=None):
        """Resolve Admin REST API endpoints."""
        if restapi:
            return [restapi]

        for scope in self.admin_api_scope:
            try:
                return self._resolve_srv('_http._tcp.adminapi.' + scope)
            except ContextError:
                pass

        raise ContextError('no admin api found.')

    def resolve(self, cellname=None):
        """Resolve Zookeeper connection string by cell name."""
        # TODO: LDAPs should be a list, and admin object shuld accept
        #                list of host:port as connection arguments rather than
        #                single host:port.
        if not cellname:
            cellname = self.cell

        if not cellname:
            raise ContextError('Cell is not specified.')

        if not self.ldap.url:
            ldap_srv_rec = dnsutils.srv('_ldap._tcp.%s.%s' % (cellname,
                                                              self.dns_domain))
            if ldap_srv_rec:
                ldap_host, ldap_port, _prio, _weight = ldap_srv_rec[0]
                self.ldap.url = 'ldap://%s:%s' % (ldap_host, ldap_port)

        while self.resolvers:
            resolver = self.resolvers.pop(0)
            resolver(cellname)
            if self.zk.url:
                break

        if not self.zk.url:
            raise ContextError('Unable to resolve cell: %s' % cellname)

        self.cell = cellname

    def _resolve_cell_from_dns(self, cellname):
        """Resolve Zookeeper connection string from DNS."""
        if not self.dns_domain:
            _LOGGER.warn('DNS domain is not set.')
            zkurl_rec = dnsutils.txt('zk.%s' % (cellname))
        else:
            zkurl_rec = dnsutils.txt('zk.%s.%s' % (cellname, self.dns_domain))

        if zkurl_rec:
            self.cell = cellname
            self.zk.url = zkurl_rec[0]

        return bool(self.zk.url)

    def _resolve_cell_from_ldap(self, cellname):
        """Resolve Zookeeper connection sting from LDAP by cell name."""
        # TODO: in case of invalid cell it will throw ldap exception.
        #                need to standardize on ContextError raised lazily
        #                on first connection attempt, and keep resolve
        #                exception free.
        admin_cell = admin.Cell(self.ldap.conn)
        try:
            cell = admin_cell.get(cellname)
            zk_hostports = [
                '%s:%s' % (master['hostname'], master['zk-client-port'])
                for master in cell['masters']
            ]
            self.zk.url = 'zookeeper://%s@%s/treadmill/%s' % (
                cell['username'],
                ','.join(zk_hostports),
                cellname
            )
            self.cell = cellname
        except ldap3.LDAPNoSuchObjectResult:
            _LOGGER.debug('Cell not defined in LDAP: %s', cellname)

        return bool(self.zk.url)


GLOBAL = Context()
