"""Watches servers zk2fs info and keeps reference to server metadata for a
particular partition.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import fnmatch
import io
import logging
import os
import sys

import ldap3
import six

from treadmill import dirwatch
from treadmill import yamlwrapper as yaml

import treadmill.ldap3kerberos

sys.modules['ldap3.protocol.sasl.kerberos'] = treadmill.ldap3kerberos

DC_KEY = 'nt.dc'
DN_KEY = 'nt.dn'

_LOGGER = logging.getLogger(__name__)


def create_ldap_connection(domain_controller):
    """Create ldap connection object.
    """
    # Disable W0212: Access to a protected member _is_ipv6 of a
    #                client class
    #
    # This is needed because twisted monkey patches socket._is_ipv6
    # and ldap3 code is wrong.
    # pylint: disable=W0212
    ldap3.Server._is_ipv6 = lambda x, y: False
    server = ldap3.Server(domain_controller, mode=ldap3.IP_V4_ONLY)

    return ldap3.Connection(
        server,
        authentication=ldap3.SASL,
        sasl_mechanism='GSSAPI',
        client_strategy=ldap3.RESTARTABLE,
        auto_bind=True,
        auto_range=True,
        return_empty_attributes=False
    )


class ServersWatch:
    """Treadmill servers watch.
    """

    __slots__ = (
        '_partition',
        '_servers',
        '_servers_path',
        '_decorated_on_created',
        '_decorated_on_modified',
        '_decorated_on_deleted',
        '_on_server_added',
        '_on_server_deleted',
        '_ldap_connections'
    )

    def __init__(self, dirwatcher_dispatcher, fs_root, partition,
                 on_server_added=None, on_server_deleted=None):
        self._servers_path = os.path.join(fs_root, 'servers')
        dirwatcher_dispatcher.dirwatcher.add_dir(self._servers_path)
        dirwatcher_dispatcher.register(self._servers_path, {
            dirwatch.DirWatcherEvent.CREATED: self._on_created,
            dirwatch.DirWatcherEvent.MODIFIED: self._on_modified,
            dirwatch.DirWatcherEvent.DELETED: self._on_deleted,
        })
        self._partition = partition
        self._servers = {}
        self._on_server_added = on_server_added
        self._on_server_deleted = on_server_deleted
        self._ldap_connections = {}

    def get_server_info(self, server_name):
        """Gets the server info the given server name or None if it does not
        exist

        :param server_name:
            The fqdn of the server
        :return:
            The server info as a `dict` or None
        """
        return self._servers.get(server_name, None)

    def get_all_server_info(self):
        """Gets all the server information which is watched.

        :return:
            A list of server information.
        """
        return list(six.itervalues(self._servers))

    def _add_ldap_connection(self, server_info):
        """Adds an ldap connection to the dictionary.

        :param server_info:
            The info about the server.
        """
        if DC_KEY not in server_info or DN_KEY not in server_info:
            return False

        dc = server_info[DC_KEY]

        if dc in self._ldap_connections:
            return True

        self._ldap_connections[dc] = create_ldap_connection(dc)

        return True

    def get_ldap_connection(self, server_info):
        """Gets an AD LDAP connection for the given server name.

        :return:
           The fqdn of the server
        :param server_info:
            The info attached to the server.
        :return:
           An `ldap3.Connection` to the host's domain controller
        """
        return self._ldap_connections[server_info[DC_KEY]]

    def _load_server_info(self, path):
        """Loads the server info from the given path.

        :param path:
            The path to the server info
        :return:
            A `dict` representing the server info or None
        """
        try:
            with io.open(path, 'r') as f:
                server_info = yaml.load(stream=f)

                if not server_info:
                    return None

                if 'partition' not in server_info:
                    return None

                if fnmatch.fnmatch(server_info['partition'], self._partition):
                    if self._add_ldap_connection(server_info):
                        hostname = os.path.basename(path)
                        server_info['hostname'] = hostname
                        _LOGGER.info('Found valid server %r', server_info)
                        return server_info

                _LOGGER.info('Found invalid server %r at path %r', server_info,
                             path)

        except OSError as err:
            _LOGGER.exception('Cannot read server info %r', path)
            if err.errno is not errno.ENOENT:
                raise
        except yaml.YAMLError:
            _LOGGER.exception('Invalid server info YAML %r', path)

        return None

    def _on_created(self, path):
        """Path created handler for dirwatch.

        :param path:
            The path that was created
        """
        server_info = self._load_server_info(path)
        if server_info is None:
            return

        server_name = os.path.basename(path)

        _LOGGER.debug('Adding server info %r - %r', server_name,
                      server_info)

        self._servers[server_name] = server_info
        if self._on_server_added is not None:
            self._on_server_added(server_info)

    def _on_modified(self, path):
        """Path modified handler for dirwatch.

        :param path:
            The path that was modified
        """
        server_name = os.path.basename(path)
        was_included = False
        if server_name in self._servers:
            _LOGGER.debug('Server info for %r exists', server_name)
            was_included = True

        server_info = self._load_server_info(path)
        if server_info is not None:
            _LOGGER.debug('Updating server info %r - %r', server_name,
                          server_info)

            self._servers[server_name] = server_info
            if not was_included and self._on_server_added is not None:
                self._on_server_added(server_info)

        elif was_included:
            server_info = self._servers[server_name]
            _LOGGER.debug('Removing server info %r - %r', server_name,
                          server_info)

            if self._on_server_deleted is not None:
                self._on_server_deleted(server_info)

            del self._servers[server_name]

    def _on_deleted(self, path):
        """Path deleted handler for dirwatch.

        :param path:
            The path that was deleted
        """
        server_name = os.path.basename(path)
        if server_name in self._servers:
            server_info = self._load_server_info(path)
            _LOGGER.debug('Removing server info %r - %r', server_name,
                          server_info)

            if self._on_server_deleted is not None:
                self._on_server_deleted(server_info)

            del self._servers[server_name]

    def sync(self):
        """Initial sync of servers."""
        for name in os.listdir(self._servers_path):
            self._on_created(os.path.join(self._servers_path, name))
