"""Unit test for treadmill.cli.metrics."""

import importlib
import os
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import click
import click.testing
import mock


# don't compain about protected member access
# pylint: disable=W0212
class MetricsTest(unittest.TestCase):
    """Mock test for treadmill.cli.metrics"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.met_mod = importlib.import_module('treadmill.cli.metrics')
        self.met_cli = self.met_mod.init()

    def test_rrdfile(self):
        """Test the _rrdfile() function."""
        self.assertEqual(
            self.met_mod._rrdfile('tmp', 'fooapp'),
            os.path.join('tmp', 'fooapp.rrd'))

        self.assertEqual(
            self.met_mod._rrdfile('tmp', 'hostname', 'metric'),
            os.path.join('tmp', 'hostname-metric.rrd'))

    def test_metrics_url(self):
        """Test the _metrics_url() function."""
        self.assertEqual(
            self.met_mod._metrics_url('some.host.com', 'proid.app#123'),
            '/nodeinfo/some.host.com/metrics/proid.app%23123')
        self.assertEqual(
            self.met_mod._metrics_url('some.host.com', 'proid.app#123/asdf'),
            '/nodeinfo/some.host.com/metrics/proid.app%23123/asdf')
        self.assertEqual(
            self.met_mod._metrics_url('some.host.com', 'webauthd'),
            '/nodeinfo/some.host.com/metrics/webauthd')

    def test_download_rrd(self):
        """Test the _download_rrd() function."""
        result = self.runner.invoke(self.met_mod._download_rrd,
                                    ['http://...', '/nodeinfo/...',
                                     'file.rrd'])
        self.assertEqual(result.exit_code, -1)

    @mock.patch('treadmill.discovery.iterator', mock.Mock(return_value=[]))
    @mock.patch('treadmill.context.GLOBAL.zk', mock.Mock())
    @mock.patch('treadmill.cli.metrics._get_nodeinfo_url',
                mock.Mock(return_value='http://...'))
    def test_metrics(self):
        """Test the metrics() command handler."""
        result = self.runner.invoke(self.met_cli, ['nosuchapp', '--outdir',
                                                   '/tmp', '--cell', 'foo'])

        self.assertEqual(result.exit_code, -1)


if __name__ == '__main__':
    unittest.main()
