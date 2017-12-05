"""
Verifies system apps are running.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import unittest

from treadmill import context
from treadmill import admin
from treadmill import checkout as chk
from treadmill import zknamespace as z


_LOGGER = logging.getLogger(__name__)


def test():
    """Create sysapps test class."""

    zkclient = context.GLOBAL.zk.conn
    cell_name = context.GLOBAL.cell
    admin_cell = admin.Cell(context.GLOBAL.ldap.conn)

    # get cell attribute from ldap object
    cell = admin_cell.get(cell_name)
    sysproid = cell['username']

    running = zkclient.get_children(z.RUNNING)
    # prefilter treadmill apps to improve efficiency
    running_set = set([name.split('#')[0] for name in running])

    class SystemAppTest(unittest.TestCase):
        """System apps checkout."""

    for appname in ['app-dns', 'cellapi', 'adminapi', 'stateapi', 'wsapi']:

        @chk.T(SystemAppTest, running_set=running_set, sysproid=sysproid,
               cell=cell_name, appname=appname)
        def _test_app_running(self, running_set, sysproid, cell, appname):
            """Check {sysproid}.{appname}.{cell} is running."""
            full_app_name = '%s.%s.%s' % (sysproid, appname, cell)
            self.assertIn(full_app_name, running_set)

    return SystemAppTest
