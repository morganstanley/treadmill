"""Watchtower App register plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import logging
import os
import socket
import stat
import struct

from treadmill import apphook
from treadmill import fs
from treadmill import supervisor

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import proiddb
from treadmill.ms import watchtower as wtapi

_LOGGER = logging.getLogger(__name__)

_WATCHTOWER = 'watchtower'
_CONTAINER_ENV_DIR = 'env'


class AppHookWatchtowerPlugin(apphook.AppHookPluginBase):
    """Watchtower App Hook plugin"""

    def __init__(self, tm_env):
        super(AppHookWatchtowerPlugin, self).__init__(tm_env)

    def init(self):
        """Initialize the plugin."""
        treadmill_root = self.tm_env.root
        wt_app_dir = os.path.join(treadmill_root, _WATCHTOWER)
        fs.mkdir_safe(wt_app_dir)

    def configure(self, app, container_dir):
        """ write watchtower app file
        """
        treadmill_root = self.tm_env.root
        filename = '%s#%s' % (app.app, app.task)
        container_file = os.path.join(treadmill_root, _WATCHTOWER, filename)
        pid = get_system_pid()
        try:
            eonid = proiddb.eonid(app.proid)
            resource_name = _get_resource_name(eonid,
                                               app.proid)
            _create_watchtower_file(container_file, app, pid, resource_name,
                                    eonid)
            env_dir = os.path.join(container_dir, _CONTAINER_ENV_DIR)
            _create_resource_env_var(env_dir, resource_name)

            return container_file
        except Exception as err:  # pylint: disable=W0703
            _LOGGER.error('unable to generate watchtower file for %s#%s: %s',
                          app.app, app.task, err)
            return None

    def cleanup(self, app, _container_dir):
        """ delete watchtower app file
        """
        treadmill_root = self.tm_env.root
        filename = '%s#%s' % (app.app, app.task)
        container_file = os.path.join(treadmill_root, _WATCHTOWER, filename)
        try:
            os.unlink(container_file)
        except OSError as err:
            # we do not care if watchtower file has been deleted
            if err.errno != errno.ENOENT:
                raise err


def _get_resource_name(eonid, proid):
    shard = wtapi.get_shard()
    return '{}-{}-{}'.format(eonid, proid, shard)


def _create_resource_env_var(env_dir, resource_name):
    """ create WT resource name in treadmill environment variable directory """
    supervisor.create_environ_dir(env_dir,
                                  {'TREADMILL_WT_RESOURCE': resource_name},
                                  update=True)


def _create_watchtower_file(target_path, app, pid, resource, eonid=None):
    """ create app file in format recognizable by WT
    """
    container_data = [
        'PID={}\n'.format(pid),
        'ENV={}\n'.format(app.environment),
        'PROID={}\n'.format(app.proid),
        'EONID={}\n'.format('' if eonid is None else str(eonid)),
        'NAME={}\n'.format(app.app),
        'INSTANCE={}\n'.format(app.task),
        'CELL={}\n'.format(app.cell),
        'RESOURCE_NAME={}\n'.format(resource)
    ]

    fs.write_safe(
        target_path,
        lambda f: f.writelines(container_data),
        mode='w',
        permission=stat.S_IWUSR | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
    )
    _LOGGER.debug('temporary file => %s', target_path)


def get_system_pid(sock_file='/var/run/unixident/ident.sock'):
    """ get process system pid from unixsocket
    """
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(sock_file)
        data = sock.recv(4)
        pid_tuple = struct.unpack('@I', data)
        pid = pid_tuple[0]
    except socket.error:
        _LOGGER.error('Fail to get system pid from %s', sock_file)
        pid = None
    finally:
        sock.close()

    return pid
