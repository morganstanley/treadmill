"""
Verifies system apps are running.
"""

import importlib
import logging
import unittest

from treadmill import context
from treadmill import admin
from treadmill import checkout as chk
from treadmill import zknamespace as z
from treadmill import zkutils

_LOGGER = logging.getLogger(__name__)


def _treadmill_root(version):
    """load cell version plugin"""
    cell_plugin = importlib.import_module('treadmill.plugins.cell_model')
    return cell_plugin.treadmill_root(version)


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

    running = zkclient.get_children(z.RUNNING)
    scheduled = zkclient.get_children(z.SCHEDULED)
    # prefilter treadmill apps to improve efficiency
    treadmill_scheduled = [s for s in scheduled if s.startswith(sysproid)]
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

        @chk.T(SystemAppTest, scheduled=treadmill_scheduled, sysproid=sysproid,
               cell=cell_name, appname=appname, treadmill=treadmill)
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
                    self.assertIn(
                        treadmill, service['command'],
                        '{0} not started by {1}'.format(ins, treadmill)
                    )

    return SystemAppTest
