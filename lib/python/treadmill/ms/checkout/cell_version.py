"""Verifies system apps are deployed correctly.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import unittest

from treadmill import admin
from treadmill import checkout as chk
from treadmill import context
from treadmill import zknamespace as z
from treadmill import zkutils

_LOGGER = logging.getLogger(__name__)


def _treadmill_root(version):
    """Returns treadmill root for given version."""
    return '/ms/dist/cloud/PROJ/treadmill/%s/common' % version


def test():
    """Create sysapps test class."""

    zkclient = context.GLOBAL.zk.conn
    cell_name = context.GLOBAL.cell
    admin_cell = admin.Cell(context.GLOBAL.ldap.conn)

    # get cell attribute from ldap object
    cell = admin_cell.get(cell_name)
    sysproid = cell['username']
    treadmill = cell.get('root')

    if treadmill is None:
        treadmill = _treadmill_root(cell['version'])

    scheduled = zkclient.get_children(z.SCHEDULED)
    # prefilter treadmill apps to improve efficiency
    treadmill_scheduled = [s for s in scheduled if s.startswith(sysproid)]

    class CellVersionTest(unittest.TestCase):
        """System apps checkout."""

    for appname in ['app-dns', 'cellapi', 'adminapi', 'stateapi', 'wsapi']:

        @chk.T(CellVersionTest, scheduled=treadmill_scheduled,
               sysproid=sysproid, cell=cell_name, appname=appname,
               treadmill=treadmill)
        def _test_app_version(self, scheduled, sysproid, cell, appname,
                              treadmill):
            """Check {sysproid}.{appname}.{cell}#xxxxxx is good version."""
            full_app_name = '%s.%s.%s' % (sysproid, appname, cell)
            # filter out non-system apps
            sys_app_instances = [ins for ins in scheduled
                                 if ins.startswith(full_app_name)]

            for ins in sys_app_instances:
                # get manifest of each instance
                manifest = zkutils.get_default(
                    zkclient, '{0}/{1}'.format(z.SCHEDULED, ins)
                )
                # treadmill service command must have correct treadmill path
                for service in manifest['services']:
                    if service['name'] == 'laas':
                        continue

                    self.assertIn(
                        treadmill, service['command'],
                        '{0} not started by {1}'.format(ins, treadmill)
                    )

    return CellVersionTest
