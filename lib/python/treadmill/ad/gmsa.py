"""GMSA manipulation.
"""

from __future__ import absolute_import

import errno
import logging
import os

import ldap3
import parse

from . import _servers as servers

from treadmill import dirwatch

_LOGGER = logging.getLogger(__name__)


class HostGroupWatch(object):
    """Treadmill GMSA placement watch.
    """

    __slots__ = (
        '_placement_path',
        '_servers_watch',
        '_dirwatcher',
        '_dirwatch_dispatcher',
        '_proids',
        '_servers',
        '_group_ou',
        '_group_pattern',
        '_synced',
    )

    def __init__(self, fs_root, partition, group_ou, group_pattern):
        fs_root = os.path.realpath(fs_root)
        self._placement_path = os.path.join(fs_root, 'placement')
        self._dirwatcher = dirwatch.DirWatcher(self._placement_path)
        self._dirwatch_dispatcher = dirwatch.DirWatcherDispatcher(
            self._dirwatcher)
        self._dirwatch_dispatcher.register(self._placement_path, {
            dirwatch.DirWatcherEvent.CREATED: self._on_created_server,
            dirwatch.DirWatcherEvent.DELETED: self._on_deleted_server,
        })
        self._dirwatch_dispatcher.register(self._placement_path + '/*', {
            dirwatch.DirWatcherEvent.CREATED: self._on_created_placement,
            dirwatch.DirWatcherEvent.DELETED: self._on_deleted_placement,
        })
        self._servers_watch = servers.ServersWatch(self._dirwatch_dispatcher,
                                                   fs_root, partition,
                                                   self._add_server,
                                                   self._remove_server)
        self._proids = {}
        self._servers = set()
        self._group_ou = group_ou
        self._group_pattern = group_pattern
        self._synced = False

    def _check_ldap3_operation(self, conn):
        """Checks that the ldap3 operation succeeded/failed.

        :param conn:
            The `ldap3.Connection` that the operation was made.
        :return:
            `True` if the operation succeed; false otherwise
        """
        result_code = conn.result['result']
        if result_code in (0, 68):
            return True

        _LOGGER.warning('Ldap operation failed %r', conn.result)
        return False

    def _get_proid(self, app):
        """Gets the name of the proid from the given application instance.

        :param app:
            The application instance name
        :return:
            The name of the proid
        """
        return app.split('.', 1)[0]

    def _get_server_dn_set(self, proid):
        """Gets the server dn set for the given proid.

        :param proid:
            The proid name.
        :return:
            A set of dn's that are assigned to the proid.
        """
        if proid in self._proids:
            return self._proids[proid]
        else:
            dn_set = set()
            self._proids[proid] = dn_set
            return dn_set

    def _get_group_name(self, proid):
        """Gets the group name from the given proid

        :param proid:
            The name of the proid.
        :return:
            The group name as a `str`
        """
        return self._group_pattern.format(proid)

    def _get_group_dn(self, proid):
        """Gets the group dn from the given proid

        :param proid:
            The name of the proid.
        :return:
            The group dn as a `str`
        """
        group_name = self._get_group_name(proid)
        return 'CN={},{}'.format(group_name, self._group_ou)

    def _add_dn_to_proid_group(self, conn, server_dn, proid, force=False):
        """Adds a placement.

        :param conn:
            The `ldap3.Connection`
        :param server_dn:
            The server server_dn
        :param proid:
            The name of the proid
        """
        server_dn_set = self._get_server_dn_set(proid)
        group = self._get_group_dn(proid)

        if not self._synced:
            _LOGGER.debug('Server %r should be in group %r', server_dn, group)
            server_dn_set.add(server_dn)
            return

        elif not force and server_dn in server_dn_set:
            return

        _LOGGER.debug('Adding %r to group %r', server_dn, group)
        conn.modify(group, {'member': [(ldap3.MODIFY_ADD, [server_dn])]})

        if self._check_ldap3_operation(conn):
            server_dn_set.add(server_dn)

    def _add_placement(self, server_info, proid):
        """Adds a placement.

        :param server_info:
            The info attached to the server
        :param proid:
            The name of the proid
        """
        dn = server_info[servers.DN_KEY]
        conn = self._servers_watch.get_ldap_connection(server_info)
        self._add_dn_to_proid_group(conn, dn, proid)

    def _remove_dn_from_proid_group(self, conn, server_dn, proid, force=False):
        """Removes a placement.

        :param conn:
            The `ldap3.Connection`
        :param server_dn:
            The server server_dn
        :param proid:
            The name of the proid
        """
        server_dn_set = self._get_server_dn_set(proid)

        if force or server_dn in server_dn_set:
            group = self._get_group_dn(proid)

            _LOGGER.debug('Removing %r from group %r', server_dn, group)
            conn.modify(group, {'member': [(ldap3.MODIFY_DELETE,
                                            [server_dn])]})

            if self._check_ldap3_operation(conn):
                server_dn_set.discard(server_dn)

    def _remove_placement(self, server_info, proid):
        """Removes a placement.

        :param server_info:
            The info attached to the server
        :param proid:
            The name of the proid
        """
        dn = server_info[servers.DN_KEY]
        conn = self._servers_watch.get_ldap_connection(server_info)
        self._remove_dn_from_proid_group(conn, dn, proid)

    def _add_server(self, server_info):
        """Add a server to the placement watcher list.

        :param server_info:
            The info attached to the server
        """
        dn = server_info[servers.DN_KEY]
        if dn in self._servers:
            return

        try:
            server_dir = os.path.join(self._placement_path,
                                      server_info['hostname'])
            self._dirwatcher.add_dir(server_dir)
            for app in os.listdir(server_dir):
                proid = self._get_proid(app)
                self._add_placement(server_info, proid)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise

        self._servers.add(dn)

    def _remove_server(self, server_info):
        """Remove a server from the placement watcher list.

        :param server_info:
            The info attached to the server
        """
        dn = server_info[servers.DN_KEY]
        if dn not in self._servers:
            return

        try:
            server_dir = os.path.join(self._placement_path,
                                      server_info['hostname'])
            self._dirwatcher.remove_dir(server_dir)
            for proid in self._proids.keys():
                server_dn_set = self._proids[proid]
                if dn in server_dn_set:
                    self._remove_placement(server_info, proid)

        except OSError as err:
            if err.errno != errno.ENOENT:
                raise

        self._servers.remove(dn)

    def _on_created_server(self, path):
        """Path created handler for dirwatch.
        """
        server_name = os.path.basename(path)
        server_info = self._servers_watch.get_server_info(server_name)
        if server_info is not None:
            self._add_server(server_info)

    def _on_created_placement(self, path):
        """Path created handler for dirwatch.
        """
        dirname = os.path.dirname(path)
        server_name = os.path.basename(dirname)
        server_info = self._servers_watch.get_server_info(server_name)
        if server_info is not None:
            proid = self._get_proid(os.path.basename(path))
            self._add_placement(server_info, proid)

    def _on_deleted_server(self, path):
        """Path deleted handler for dirwatch.
        """
        server_name = os.path.basename(path)
        server_info = self._servers_watch.get_server_info(server_name)
        self._remove_server(server_info)

    def _on_deleted_placement(self, path):
        """Path deleted handler for dirwatch.
        """
        dirname = os.path.dirname(path)
        server_name = os.path.basename(dirname)
        server_info = self._servers_watch.get_server_info(server_name)
        proid = self._get_proid(os.path.basename(path))
        self._remove_placement(server_info, proid)

    def _sync(self):
        """Initial sync of placement."""
        self._servers_watch.sync()
        self._synced = True

        dn_mapping = {}
        conn = None
        for server_info in self._servers_watch.get_all_server_info():
            dn_mapping[server_info[servers.DN_KEY]] = server_info

            if conn is None:
                conn = self._servers_watch.get_ldap_connection(server_info)

        if conn is None:
            _LOGGER.error('No ldap connection information available')
            return

        conn.search(
            search_base=self._group_ou,
            search_filter='(objectclass=group)',
            attributes=['samAccountName', 'member']
        )

        if not self._check_ldap3_operation(conn):
            _LOGGER.error('Failed to get groups from AD')
            return

        all_proids = {}
        for entry in conn.response:
            match = parse.parse(self._group_pattern,
                                entry['attributes']['samAccountName'][0])

            members = set()
            if 'member' in entry['attributes']:
                members = set(entry['attributes']['member'])

            all_proids[match[0]] = members

        for proid in all_proids.keys():
            server_dn_set = self._get_server_dn_set(proid)
            actual_dn_set = all_proids[proid]
            _LOGGER.debug('Sync proid %s, expected %r - actual %r', proid,
                          server_dn_set, actual_dn_set)

            diff = server_dn_set.symmetric_difference(actual_dn_set)
            for dn in diff:
                if dn not in dn_mapping:
                    continue

                if dn in server_dn_set:
                    self._add_dn_to_proid_group(conn, dn, proid, force=True)
                else:
                    self._remove_dn_from_proid_group(conn, dn, proid,
                                                     force=True)

    def run(self):
        """Sync and start listening for changes."""
        self._sync()

        running = True
        while running:
            if self._dirwatcher.wait_for_events():
                self._dirwatcher.process_events()
