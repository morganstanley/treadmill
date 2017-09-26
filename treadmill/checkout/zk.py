"""Verifies health of Zookeeper.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import logging

from treadmill import context
from treadmill import admin
from treadmill import checkout as chk


_LOGGER = logging.getLogger(__name__)


class ZookeeperTest(unittest.TestCase):
    """Zookeeper checkout."""

    def test_zookeeper_connection(self):
        """Checks connection status."""
        context.GLOBAL.zk.conn.get_children('/scheduled')

    def test_ruok(self):
        """Checks ensemble health."""
        admin_cell = admin.Cell(context.GLOBAL.ldap.conn)
        cell = admin_cell.get(context.GLOBAL.cell)

        actual = 0
        idx = 0
        for idx, master in enumerate(cell['masters']):
            hostname = master['hostname']
            port = master['zk-client-port']
            try:
                zk_status = chk.zkadmin(hostname, port, 'ruok\n')
                print('%s:%s' % (hostname, port), zk_status)
                actual = actual + 1
            except Exception as err:  # pylint: disable=W0703
                print(str(err))

        expected = idx + 1
        self.assertEqual(actual, expected, 'Not all ensemble members are up.')
