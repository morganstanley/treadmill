"""Treadmill context.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import functools
import logging
import os
import socket

from treadmill import plugin_manager

_LOGGER = logging.getLogger(__name__)


class ContextError(Exception):
    """Raised when unable to connect to LDAP or Zookeeper.
    """


def required(msg):
    """Raises error if return value of function is None.
    """

    def _decorator(func):
        """Actual decorator.
        """

        @functools.wraps(func)
        def decorated_function(*args, **kwargs):
            """Decorated function, checks result is not None.
            """
            result = func(*args, **kwargs)
            if result is None:
                raise ContextError(msg)
            return result

        return decorated_function

    return _decorator


def _norm(cellname):
    """Normalize cell name."""
    return cellname.upper().replace('-', '_')


class EnvContext:
    """Environment variable context.
    """

    __slots__ = (
        '_context',
    )

    def __init__(self, ctx):
        self._context = ctx

    def resolve(self, ctx, attr):
        """URL Resolve attribute from DNS.
        """
        # TODO: consider migrating zk_url adn ldap_url to environment context.
        #
        #       The problem is that TREADMILL_ZOOKEEPER is used everywhere,
        #       and based on the impl, it should be dictionary by cell name.
        _resolvers = {
            'admin_api': self._admin_api,
            'cell_api': self._cell_api,
            'state_api': self._state_api,
            'ws_api': self._ws_api,
        }

        value = _resolvers[attr](ctx)
        _LOGGER.debug('Environment override for attr: %s - %s', attr, value)
        return value

    def _admin_api(self, ctx):
        """Return admin api from environment variable."""
        del ctx
        return os.environ['TREADMILL_ADMINAPI'].split(',')

    def _cell_api(self, ctx):
        """Return cell api from environment variable."""
        return os.environ['TREADMILL_CELLAPI_' + _norm(ctx.cell)].split(',')

    def _ws_api(self, ctx):
        """Return websocket api from environment variable."""
        return os.environ['TREADMILL_WSAPI_' + _norm(ctx.cell)].split(',')

    def _state_api(self, ctx):
        """Return state api from environment variable."""
        return os.environ['TREADMILL_STATEAPI_' + _norm(ctx.cell)].split(',')


class DnsContext:
    """DNS context.
    """

    __slots__ = (
        '_context',
        '_dns',
    )

    def __init__(self, ctx):
        self._context = ctx
        self._dns = None

    @property
    def _resolver(self):
        if self._dns is not None:
            return self._dns

        dns = plugin_manager.load('treadmill.context', 'dns')
        dns.init(self._context)
        self._dns = dns
        return self._dns

    def admin_api_srv(self):
        """Get Admin API SRV record data.
        """
        (srv_entry, _proto) = self._resolver.lookup(
            self._context,
            'admin_api'
        )
        return srv_entry

    def state_api_srv(self, cell):
        """Get State API SRV record data.
        """
        (srv_entry, _proto) = self._resolver.lookup(
            self._context,
            'state_api',
            scope=self._resolver.cell_scope(cell)
        )
        return srv_entry

    def cell_api_srv(self, cell):
        """Get Cell API SRV record data.
        """
        (srv_entry, _proto) = self._resolver.lookup(
            self._context,
            'cell_api',
            scope=self._resolver.cell_scope(cell)
        )
        return srv_entry

    def ws_api_srv(self, cell):
        """Get Websocket API SRV record data.
        """
        (srv_entry, _proto) = self._resolver.lookup(
            self._context,
            'ws_api',
            scope=self._resolver.cell_scope(cell)
        )
        return srv_entry


class AdminContext:
    """Ldap context.
    """

    __slots__ = (
        '_context',
        '_conn',
    )

    def __init__(self, ctx):
        self._context = ctx
        self._conn = None

    @property
    @required('Cannot resolve LDAP suffix.')
    def ldap_suffix(self):
        """LDAP suffix getter.
        """
        return self._context.get('ldap_suffix', resolve=False)

    @property
    def user(self):
        """User, getter.
        """
        return self._context.get('ldap_user', resolve=False)

    @user.setter
    def user(self, value):
        """User, setter.
        """
        if value != self._context.get('ldap_user', resolve=False):
            self._conn = None
        self._context.set('ldap_user', value)

    @property
    def password(self):
        """Password, getter.
        """
        return self._context.get('ldap_pwd', resolve=False)

    @password.setter
    def password(self, value):
        """Password, setter.
        """
        self._context.set('ldap_pwd', value)
        if self.user is None:
            self.user = 'cn=Manager,%s' % self.ldap_suffix

    @property
    @required('Cannot resolve LDAP url.')
    def url(self):
        """URL, getter.
        """
        return self._context.get('ldap_url', resolve=True)

    @url.setter
    def url(self, value):
        """Set URL, then nullify the connection.
        """
        self._context.set('ldap_url', value)
        self._conn = None

    @property
    def write_url(self):
        """Get the LDAP server URL for write access.
        """
        url = self._context.get('ldap_write_url', resolve=True)
        return url

    @write_url.setter
    def write_url(self, value):
        """Set the LDAP server URL for write access.
        """
        self._context.set('ldap_write_url', value)
        self._conn = None

    @property
    def conn(self):
        """Lazily establishes connection to admin LDAP.
        """
        if self._conn:
            return self._conn

        plugin = plugin_manager.load('treadmill.context', 'admin')
        self._conn = plugin.connect(self.url, self.write_url, self.ldap_suffix,
                                    self.user, self.password)
        return self._conn

    def partition(self):
        """Return admin Partition object.
        """
        return self.conn.partition()

    def allocation(self):
        """Return admin Allocation object.
        """
        return self.conn.allocation()

    def cell_allocation(self):
        """Return admin CellAllocation object.
        """
        return self.conn.cell_allocation()

    def tenant(self):
        """Return admin Tenant object.
        """
        return self.conn.tenant()

    def cell(self):
        """Return admin Cell object.
        """
        return self.conn.cell()

    def application(self):
        """Return admin Application object.
        """
        return self.conn.application()

    def app_group(self):
        """Return admin AppGroup object.
        """
        return self.conn.app_group()

    def dns(self):
        """Return admin DNS object.
        """
        return self.conn.dns()

    def server(self):
        """Return admin Server object.
        """
        return self.conn.server()


class ZkContext:
    """Zookeeper context.
    """

    __slots__ = (
        '_context',
        '_conn',
        '_listeners',
        'idpath',
    )

    def __init__(self, ctx):
        self._context = ctx
        self._conn = None
        self._listeners = []
        self.idpath = None

    def add_listener(self, listener):
        """Add a listener.
        """
        self._listeners.append(listener)

    @property
    @required('Cannot resolve Zookeeper connection string.')
    def url(self):
        """Resolves and return context zk url.
        """
        return self._context.get('zk_url', resolve=True)

    @url.setter
    def url(self, value):
        """Sets context zk url.
        """
        self._context.set('zk_url', value)

    @property
    def conn(self):
        """Lazily creates Zookeeper client.
        """
        if self._conn:
            return self._conn

        _LOGGER.debug('Connecting to Zookeeper %s', self.url)

        plugin = plugin_manager.load('treadmill.context', 'zookeeper')
        self._conn = plugin.connect(self.url, idpath=self.idpath)
        if self._listeners:
            for listener in self._listeners:
                self._conn.add_listener(listener)

        return self._conn

    @conn.setter
    def conn(self, zkclient):
        """Explicitely set connection."""
        self._conn = zkclient

    def has_conn(self):
        """Returns True if Zookeeper client has been created, False otherwise.
        """
        return self._conn is not None


class Context:
    """Global connection context.
    """

    __slots__ = (
        'ldap',
        'admin',
        'zk',
        'dns',
        '_resolvers',
        '_plugins',
        '_profile',
        '_profile_name',
        '_defaults',
        '_stack',
    )

    def __init__(self):
        self._profile_name = None
        self._profile = {}
        self._defaults = None
        self._plugins = []

        # Protect against recursive gets
        self._stack = set()

        # Lazy connections to Zookeeper, LDAP and DNS
        self.zk = ZkContext(self)
        self.admin = AdminContext(self)
        self.dns = DnsContext(self)

        # backward compatibility
        self.ldap = self.admin

    def _load_profile(self):
        """Loads the profile.
        """
        # Load once.
        if self._defaults is not None:
            return

        self._defaults = {
            'dns_domain': '.'.join(socket.getfqdn().split('.')[1:])
        }

        if self._profile_name:
            try:
                profile_mod = plugin_manager.load('treadmill.profiles',
                                                  self._profile_name)
                self._defaults.update(profile_mod.PROFILE)
            except KeyError:
                _LOGGER.warning('Profile not found: %s', self._profile_name)

    def _init_plugins(self):
        """Initialize plugins.
        """
        if self._plugins:
            return

        _LOGGER.debug('Loading plugins.')

        # TODO: Thsi is a hack, need a better way to determine if plugin
        #       should be loaded.
        if self.get('dns_domain', resolve=False):
            _LOGGER.debug('Loading dns plugin.')
            dns = plugin_manager.load('treadmill.context', 'dns')
            dns.init(self)
            self._plugins.append(dns)

        if self.get('ldap_url', resolve=False):
            _LOGGER.debug('Loading admin plugin.')
            ldap = plugin_manager.load('treadmill.context', 'admin')
            ldap.init(self)
            self._plugins.append(ldap)

        # Last plugin wins, so environment variables are evaluated last.
        self._plugins.append(EnvContext(self))

    def get(self, attr, default=None, resolve=True, volatile=False):
        """Get attribute from profile or defaults.
        """
        if attr in self._profile:
            return self._profile[attr]

        self._load_profile()

        if resolve and attr not in self._stack:
            self._stack.add(attr)
            try:
                self._init_plugins()
                for plugin in self._plugins:
                    try:
                        self._profile[attr] = plugin.resolve(self, attr)
                    except ContextError as err:
                        _LOGGER.warning(
                            'Error resolving attribute %s in %s: %s',
                            attr, plugin, err
                        )
                    except KeyError:
                        # Plugin is not responsible fot the attribute.
                        pass
            finally:
                self._stack.discard(attr)

        if attr not in self._profile:
            # Attr was not found, look for it in _defaults
            if (self._defaults is not None and
                    self._defaults.get(attr) is not None):
                self._profile[attr] = self._defaults[attr]

        if attr not in self._profile and default is not None:
            self._profile[attr] = default

        # The end of the function attribute is recorded in the profile and
        # never evaluated again.
        #
        # volatile attributes are evaluated all the time.
        if volatile:
            return self._profile.pop(attr, default)
        else:
            return self._profile.get(attr, default)

    def set(self, attr, value):
        """Set profile attribute.
        """
        self._profile[attr] = value

    def set_profile_name(self, profile_name):
        """Sets current profile.
        """
        self._profile_name = profile_name

    def get_profile_name(self):
        """Returns profile name.
        """
        if not self._profile_name:
            # If profile is not ambigous, use it.
            profiles = plugin_manager.names('treadmill.profiles')
            if len(profiles) == 1:
                self._profile_name = profiles[0]

        return self._profile_name

    @property
    def profile(self):
        """Returns the profile name.
        """
        self._load_profile()
        return self._profile

    @property
    @required('Cannot resolve cell.')
    def cell(self):
        """Returns cell name.
        """
        return self.get('cell', resolve=False)

    @cell.setter
    def cell(self, value):
        """Sets cell name.
        """
        self.set('cell', value)

    @property
    @required('Cannot resolve DNS domain.')
    def dns_domain(self):
        """Returns DNS domain.
        """
        return self.get('dns_domain', resolve=False)

    @dns_domain.setter
    def dns_domain(self, value):
        """Sets DNS domain.
        """
        self.set('dns_domain', value)

    @property
    def dns_server(self):
        """Returns DNS server.
        """
        return self.get('dns_server')

    @dns_server.setter
    def dns_server(self, value):
        """Sets DNS server.
        """
        return self.set('dns_server', value)

    @property
    @required('Cannot resolve LDAP suffix.')
    def ldap_suffix(self):
        """Returns LDAP suffix.
        """
        return self.get('ldap_suffix')

    @ldap_suffix.setter
    def ldap_suffix(self, value):
        """Sets DNS server.
        """
        return self.set('ldap_suffix', value)

    def scopes(self):
        """Returns supported scopes.
        """
        return self.get('scopes', ['cell'])

    @required('Cannot resolve admin api.')
    def admin_api(self, api=None):
        """Returns admin API.
        """
        if api:
            return [api]

        return self.get('admin_api', volatile=True)

    @required('Cannot resolve cell api.')
    def cell_api(self, api=None):
        """Returns cell API.
        """
        if api:
            return [api]

        return self.get('cell_api', volatile=True)

    @required('Cannot resolve websocket api.')
    def ws_api(self, api=None):
        """Returns cell API.
        """
        if api:
            return [api]

        return self.get('ws_api', volatile=True)

    @required('Cannot resolve state api.')
    def state_api(self, api=None):
        """Returns cell API.
        """
        if api:
            return [api]

        return self.get('state_api', volatile=True)


GLOBAL = Context()
