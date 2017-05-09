"""
Verifies system apps are running.
"""

import unittest
import os
import pwd

from treadmill import context
from treadmill import checkout as chk


def test():
    """Create sysapps test class."""

    zkclient = context.GLOBAL.zk.conn
    cell = context.GLOBAL.cell
    sysproid = os.environ.get('TREADMILL_ID', pwd.getpwuid(os.getuid())[0])
    running = zkclient.get_children('/running')
    running_set = set([name.split('#')[0] for name in running])

    class SystemAppTest(unittest.TestCase):
        """System apps checkout."""

    for appname in ['app-dns', 'cellapi', 'adminapi', 'stateapi', 'wsapi']:

        @chk.T(SystemAppTest, running_set=running_set, sysproid=sysproid,
               cell=cell, appname=appname)
        def _test_app_running(self, running_set, sysproid, cell, appname):
            """Check {sysproid}.{appname}.{cell} is running."""
            self.assertIn('%s.%s.%s' % (sysproid, appname, cell), running_set)

    return SystemAppTest
