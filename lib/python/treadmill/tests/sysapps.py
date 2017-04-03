"""
Verifies system apps are running.
"""

import unittest
import os
import pwd

from treadmill import context
from treadmill import tests as chk


def mk_test_app_running(running_set, sysproid, cell, appname):
    """Return test function."""

    def test_app_running(self):
        """Check app is running."""
        self.assertIn('%s.%s.%s' % (sysproid, appname, cell), running_set)

    test_app_running.__doc__ = '%s.%s is running' % (sysproid, appname)
    return test_app_running


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
        chk.add_test(
            SystemAppTest,
            mk_test_app_running(running_set, sysproid, cell, appname),
            '{}_{}_is_running.', sysproid, appname
        )

    return SystemAppTest
