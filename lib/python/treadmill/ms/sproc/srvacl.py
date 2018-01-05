"""Treadmill ZK ACL synchronization daemon.

Syncs server acls file with /servers node.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os
import time

import click

from treadmill import context
from treadmill import fs
from treadmill import utils
from treadmill import zknamespace as z

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms.plugins import zookeeper as zk

_LOGGER = logging.getLogger(__name__)


def sync_server_acls(aclfile):
    """Syncronize server acls."""
    _LOGGER.info('Starting server acl sync: %s', aclfile)

    fs.mkdir_safe(os.path.dirname(aclfile))
    zkclient = context.GLOBAL.zk.conn

    @zkclient.ChildrenWatch(z.SERVERS)
    @utils.exit_on_unhandled
    def _server_watch(servers):
        """Watch application placement."""
        _LOGGER.info('Syncronizing servers acl file: %s', aclfile)
        tmpacl = aclfile + '.tmp'
        with io.open(tmpacl, 'w') as f:
            for server in servers:
                _LOGGER.info('server: %s', server)
                name, realm = zk.get_princ_realm(server)
                f.write('{0}@{1}\n'.format(name, realm))
            f.write('\n')
        os.rename(tmpacl, aclfile)
        _LOGGER.info('Done.')

    while True:
        time.sleep(1000000)


def init():
    """Return top level command handler."""

    @click.command()
    @click.option('--zookeeper', required=True, envvar='TREADMILL_ZOOKEEPER')
    @click.argument('aclfile', required=True)
    def top(zookeeper, aclfile):
        """Sync Zookeeper ACL files."""
        context.GLOBAL.zk.url = zookeeper
        sync_server_acls(aclfile)

    return top
