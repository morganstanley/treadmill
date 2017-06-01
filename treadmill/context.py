"""Treadmill context."""

import importlib
import logging
import random

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
        'ldap_suffix',
        '_user',
        '_password',
        '_url',
        '_conn',
        '_resolve',
    )

    def __init__(self, resolve=None, user=None, password=None):
        self.ldap_suffix = None
        self._user = None
        self._password = None

        if password:
            self.password = password

        if user:
            self.user = user

        self._url = None
        self._conn = None
        self._resolve = resolve

    @property
    def user(self):
        """User, getter."""
        return self._user

    @user.setter
    def user(self, value):
        """User, setter."""
        if value != self._user:
            self._conn = None
        self._user = value

    @property
    def password(self):
        """Password, getter."""
        return self._password

    @password.setter
    def password(self, value):
        """Password, setter."""
        self._password = value
        if self._user is None:
            self.user = 'cn=Manager,%s' % self.ldap_suffix

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
            if self.ldap_suffix is None:
                raise ContextError('LDAP suffix is not set.')

            if self.url is None:
                if self._resolve:
                    self._resolve()
                if self.url is None:
                    raise ContextError('LDAP url not set.')

            _LOGGER.debug('Connecting to LDAP %s, %s',
                          self.url, self.ldap_suffix)

            self._conn = admin.Admin(self.url, self.ldap_suffix,
                                     user=self.user, password=self.password)
            self._conn.connect()

        return self._conn


class ZkContext(object):
    """Zookeeper context."""
    __slots__ = (
        'url',
        'proid',
        '_conn',
        '_resolve',
        '_listeners',
    )

    def __init__(self, resolve=None):
        self.url = None
        self.proid = None
        self._conn = None
        self._resolve = resolve
        self._listeners = []

    def add_listener(self, listener):
        """Add a listener"""
        self._listeners.append(listener)

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

            if self._listeners:
                for listener in self._listeners:
                    self._conn.add_listener(listener)

        return self._conn


class Context(object):
    """Global connection context."""
    __slots__ = (
        'cell',
        'ldap',
        'zk',
        'dns_domain',
        'dns_server',
        'admin_api_scope',
        'ctx_plugin',
        'resolvers',
    )

    def __init__(self):
        self.cell = None
        self.dns_domain = None
        self.dns_server = None
        self.ldap = AdminContext(self.resolve)
        self.zk = ZkContext(self.resolve)
        self.admin_api_scope = (None, None)
        self.ctx_plugin = None

        try:
            self.ctx_plugin = importlib.import_module(
                'treadmill.plugins.context')
            self.dns_domain = self.ctx_plugin.dns_domain()
            self.admin_api_scope = self.ctx_plugin.api_scope()
            self.ldap.ldap_suffix = self.ctx_plugin.ldap_suffix()
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

        result = dnsutils.srv(
            srv_rec + '.' + self.dns_domain, self.dns_server
        )
        random.shuffle(result)
        return result

    def _srv_to_urls(self, srv_recs, protocol=None):
        """Randomizes and converts SRV records to URLs."""
        _LOGGER.debug('Result: %r', srv_recs)

        return [dnsutils.srv_rec_to_url(srv_rec,
                                        protocol=protocol)
                for srv_rec in srv_recs]

    def cell_api_srv(self, cellname):
        """Resolve REST API SRV records."""

        target = '_http._tcp.cellapi.{}.cell'.format(cellname)
        srv_recs = self._resolve_srv(target)

        if not srv_recs:
            raise ContextError('No srv records found: %s' % target)

        return srv_recs

    def cell_api(self, restapi=None):
        """Resolve REST API endpoints."""
        if restapi:
            return [restapi]

        if not self.cell:
            raise ContextError('Cell is not specified.')

        return self._srv_to_urls(self.cell_api_srv(self.cell),
                                 'http')

    def state_api_srv(self, cellname):
        """Resolve state API SRV records."""
        target = '_http._tcp.stateapi.{}.cell'.format(cellname)
        srv_recs = self._resolve_srv(target)

        if not srv_recs:
            raise ContextError('No srv records found: %s' % target)

        return srv_recs

    def state_api(self, restapi=None):
        """Resolve state API endpoints."""
        if restapi:
            return [restapi]

        if not self.cell:
            raise ContextError('Cell is not specified.')

        return self._srv_to_urls(self.state_api_srv(self.cell),
                                 'http')

    def ws_api_srv(self, cellname):
        """Resolve state API SRV records."""
        target = '_ws._tcp.wsapi.{}.cell'.format(cellname)
        srv_recs = self._resolve_srv(target)

        if not srv_recs:
            raise ContextError('No srv records found: %s' % target)

        return srv_recs

    def ws_api(self, wsapi=None):
        """Resolve state API endpoints."""
        if wsapi:
            return [wsapi]

        if not self.cell:
            raise ContextError('Cell is not specified.')

        return self._srv_to_urls(self.ws_api_srv(self.cell),
                                 'ws')

    def admin_api_srv(self):
        """Resolve admin API SRV records."""
        for scope in self.admin_api_scope:
            try:
                result = self._resolve_srv('_http._tcp.adminapi.' + scope)
                if result:
                    return result
            except ContextError:
                pass

        raise ContextError('no admin api found.')

    def admin_api(self, restapi=None):
        """Resolve Admin REST API endpoints."""
        if restapi:
            return [restapi]

        return self._srv_to_urls(self.admin_api_srv(), 'http')

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
            ldap_srv_rec = dnsutils.srv(
                '_ldap._tcp.%s.%s' % (cellname, self.dns_domain),
                self.dns_server
            )
            self.ldap.url = ','.join([
                'ldap://%s:%s' % (rec[0], rec[1])
                for rec in ldap_srv_rec
            ])

        cell_resolved = False
        while self.resolvers and not cell_resolved:
            resolver = self.resolvers.pop(0)
            cell_resolved = resolver(cellname)

        if not cell_resolved:
            raise ContextError('Unable to resolve cell: %s' % cellname)

        self.cell = cellname

    def _resolve_cell_from_dns(self, cellname):
        """Resolve Zookeeper connection string from DNS."""
        if not self.dns_domain:
            _LOGGER.warn('DNS domain is not set.')
            zkurl_rec = dnsutils.txt('zk.%s' % (cellname), self.dns_server)
        else:
            zkurl_rec = dnsutils.txt(
                'zk.%s.%s' % (cellname, self.dns_domain),
                self.dns_server
            )

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
            exception = ContextError(
                'Cell not defined in LDAP {}'.format(cellname)
            )
            _LOGGER.debug(str(exception))
            raise exception

        return bool(self.zk.url)


GLOBAL = Context()
