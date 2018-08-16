"""Unit test Treadmill CLI.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click
import click.testing
import mock

from treadmill import context
import treadmill.cli.configure
import treadmill.cli.discovery
import treadmill.cli.sproc
import treadmill.cli.admin.blackout
import treadmill.cli.admin.ldap
import treadmill.cli.admin.show
import treadmill.cli.admin.scheduler
import treadmill.sproc.zk2fs


def check_help(testcase, args):
    """Checks help invocation."""
    run = testcase.runner.invoke(testcase.cli, args + ['--help'])
    testcase.assertEqual(
        run.exit_code, 0
    )


class TreadmillShowTest(unittest.TestCase):
    """Mock test for 'treadmill show' CLI"""

    def setUp(self):
        context.GLOBAL.dns_domain = 'xxx.com'
        self.module = treadmill.cli.admin.show
        self.runner = click.testing.CliRunner()
        self.cli = self.module.init()

    def test_help(self):
        """Test help with no arguments."""
        check_help(self, [])
        check_help(self, ['--cell', '-', 'pending'])

    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_action(self):
        """Test show actions."""
        self.runner.invoke(
            self.cli, ['--cell', 'foo', 'running'])
        self.assertEqual(context.GLOBAL.cell, 'foo')


class TreadmillSchedulerTest(unittest.TestCase):
    """Mock test for 'treadmill scheduler' CLI"""

    def setUp(self):
        context.GLOBAL.dns_domain = 'xxx.com'
        self.module = treadmill.cli.admin.scheduler
        self.runner = click.testing.CliRunner()
        self.cli = self.module.init()

    def test_help(self):
        """Test help with no arguments."""
        check_help(self, [])
        check_help(self, ['--cell', '-', 'view'])
        check_help(self, ['--cell', '-', 'view', 'allocs'])
        check_help(self, ['--cell', '-', 'view', 'servers'])
        check_help(self, ['--cell', '-', 'view', 'apps'])

    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_action(self):
        """Test scheduler commands."""
        self.runner.invoke(
            self.cli, ['--cell', 'foo', 'view', 'servers'])
        self.assertEqual(context.GLOBAL.cell, 'foo')


class TreadmillBlackoutTest(unittest.TestCase):
    """Mock test for 'treadmill blackout' CLI"""

    def setUp(self):
        context.GLOBAL.dns_domain = 'xxx.com'
        self.module = treadmill.cli.admin.blackout
        self.runner = click.testing.CliRunner()
        self.cli = self.module.init()

    def test_help(self):
        """Test help with no arguments."""
        check_help(self, [])
        check_help(self, ['--cell', '-', 'app'])
        check_help(self, ['--cell', '-', 'server'])


class TreadmillAdminLdapTest(unittest.TestCase):
    """Mock test for 'treadmill admin ldap' CLI"""

    def setUp(self):
        context.GLOBAL.dns_domain = 'xxx.com'
        self.module = treadmill.cli.admin.ldap
        self.runner = click.testing.CliRunner()
        self.cli = self.module.init()

    def test_help(self):
        """Test help with no arguments."""
        check_help(self, [])


class TreadmillConfigureTest(unittest.TestCase):
    """Mock test for 'treadmill configure' CLI"""

    def setUp(self):
        context.GLOBAL.dns_domain = 'xxx.com'
        self.module = treadmill.cli.configure
        self.runner = click.testing.CliRunner()
        self.cli = self.module.init()

    def test_help(self):
        """Test help with no arguments."""
        check_help(self, [])


class TreadmillDiscoveryTest(unittest.TestCase):
    """Mock test for 'treadmill configure' CLI"""

    def setUp(self):
        context.GLOBAL.dns_domain = 'xxx.com'
        self.module = treadmill.cli.discovery
        self.runner = click.testing.CliRunner()
        self.cli = self.module.init()

    def test_help(self):
        """Test help with no arguments."""
        check_help(self, [])


class TreadmillSprocTest(unittest.TestCase):
    """Mock test for 'treadmill configure' CLI"""

    def setUp(self):
        context.GLOBAL.dns_domain = 'xxx.com'
        self.module = treadmill.cli.sproc
        self.runner = click.testing.CliRunner()
        self.cli = self.module.init()

    @unittest.skip('XXX: CLI always return -1')
    def test_help(self):
        """Test help with no arguments."""
        check_help(self, [])

    def test_args(self):
        """Test passing context arguments."""
        self.runner.invoke(
            self.cli, ['--cell', 'foo', 'init', '--help'])
        self.assertEqual(context.GLOBAL.cell, 'foo')
        self.runner.invoke(
            self.cli, ['--cell', 'xxx', '--zookeeper', 'bla',
                       'init', '--help'])
        self.assertEqual(context.GLOBAL.cell, 'xxx')
        self.assertEqual(context.GLOBAL.zk.url, 'bla')


class TreadmillZk2FsTest(unittest.TestCase):
    """Mock test for 'treadmill configure' CLI"""

    def setUp(self):
        context.GLOBAL.dns_domain = 'xxx.com'
        self.module = treadmill.sproc.zk2fs
        self.runner = click.testing.CliRunner()
        self.cli = self.module.init()

    def test_help(self):
        """Test help with no arguments."""
        check_help(self, [''])


if __name__ == '__main__':
    unittest.main()
