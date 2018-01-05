"""Common Zapp operations.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging
import os

import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

_SAL = '/ms/dist/sam/PROJ/sal/prod/bin/sal'

_WIPE_CMD = 'Mark for wipe'
_BACKUP_LDAP_CMD = 'Backup treadmill_ldap'

_LOGGER = logging.getLogger(__name__)


def cell2plant(cell):
    """Resolve plant for given cell from environment."""
    plants_env = os.environ.get('TREADMILL_ZAPP_PLANTS')
    if not plants_env:
        raise Exception('TREADMILL_ZAPP_PLANTS not set. module load?')

    plants = dict([key_value.split('=')
                   for key_value in plants_env.split(':')])
    plant = plants.get(cell)
    if not plant:
        raise Exception('Must specify --plant or set TREADMILL_ZAPP_PLANTS')

    return plant


class Zapp(object):
    """Manage zapp plant."""

    def __init__(self, cell, plant):
        self.cell = cell
        self.plant = plant

    def _node_app(self, server):
        """Return zapp app name for the server."""
        return '{}-node-{}'.format(self.cell, server)

    def _master_app(self, server, idx):
        """Return zapp app nanme for the master."""
        return '{}-master-{}-{}'.format(self.cell, idx, server)

    def _ldap_app(self, server, port):
        """Return zapp app nanme for an LDAP"""
        return 'ldap-{}:{}'.format(server, port)

    def _control_app(self, command, app):
        """Stop app in zapp."""
        command = [_SAL, command, 'application',
                   '--name', app,
                   '--plantid', self.plant]

        _LOGGER.debug('%s', ' '.join(command))
        subprocess.check_call(command)

    def _get_cmd(self, noun, app=None):
        """Stop app in zapp."""
        command = [_SAL, 'get', noun,
                   '--plantid', self.plant,
                   '--format', 'json',
                   '-echo', '0', ]

        if app:
            command.extend(['--name', app])

        _LOGGER.debug('%s', ' '.join(command))
        return subprocess.check_output(command)

    def _control_custom_command(self, command, app):
        """Send custom command to zapp."""
        cmd = [
            _SAL, 'execute', 'prog',
            '--identifier', app,
            '--plantid', self.plant,
            '-command', command,
            '-type', 'App',
            '-echo', '0',
        ]

        _LOGGER.debug('%s', ' '.join(cmd))
        subprocess.check_call(cmd)

    def stop_master(self, servername, idx):
        """Stop master in zapp."""
        self._control_app('stop', self._master_app(servername, idx))

    def start_master(self, servername, idx):
        """Start master in zapp."""
        self._control_app('start', self._master_app(servername, idx))

    def restart_master(self, servername, idx):
        """Restart master in zapp."""
        self._control_app('restart', self._master_app(servername, idx))

    def stop_server(self, servername):
        """Stop server in zapp."""
        self._control_app('stop', self._node_app(servername))

    def start_server(self, servername):
        """Stop server in zapp."""
        self._control_app('start', self._node_app(servername))

    def mark_server_for_wipe(self, servername):
        """Mark server for clean start."""
        self._control_custom_command(_WIPE_CMD, self._node_app(servername))

    def backup_ldap(self, servername, port):
        """Mark server for clean start."""
        self._control_custom_command(
            _BACKUP_LDAP_CMD, self._ldap_app(servername, port)
        )

    def stop_ldap(self, servername, port):
        """Stop an LDAP server"""
        self._control_app('stop', self._ldap_app(servername, port))

    def start_ldap(self, servername, port):
        """Start an LDAP server"""
        self._control_app('start', self._ldap_app(servername, port))

    def ldap_app_exists(self, servername, port):
        """Determine if LDAP app exists in Zapp"""
        state_jstr = self._get_cmd(
            'appState', self._ldap_app(servername, port)
        )

        state = json.loads(state_jstr)

        if state['Result'] == 0:
            return False

        return True
