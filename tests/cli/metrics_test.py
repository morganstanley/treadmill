"""Unit test for treadmill.cli.metrics."""

import importlib
import os
import unittest

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

    def test_download_rrd(self):
        """Test the _download_rrd() function."""
        result = self.runner.invoke(self.met_mod._download_rrd,
                                    ['http://...', '/nodeinfo/...',
                                     'file.rrd'])
        self.assertEqual(result.exit_code, -1)

    @mock.patch('treadmill.cli.metrics._find_running_instance',
                mock.Mock(return_value={}))
    @mock.patch('treadmill.cli.metrics._find_uniq_instance',
                mock.Mock(return_value={}))
    @mock.patch('treadmill.cli.metrics._find_nodeinfo_endpoints',
                mock.Mock(return_value={}))
    def test_no_instance_found(self):
        """Test the exit code when no instance can be found."""
        result = self.runner.invoke(self.met_cli,
                                    ['--outdir', '/tmp', '--cell', 'foo',
                                     'running', 'proid.nosuchapp*'])
        self.assertEqual(result.exit_code, -1)

        result = self.runner.invoke(self.met_cli,
                                    ['--outdir', '/tmp', '--cell', 'foo',
                                     'app', 'proid.nosuchapp#12/asdf'])
        self.assertEqual(result.exit_code, -1)

    @mock.patch('treadmill.cli.metrics._find_running_instance',
                mock.Mock(return_value={'proid.app#123': 'foo.host.com'}))
    @mock.patch('treadmill.cli.metrics._find_nodeinfo_endpoints',
                mock.Mock(return_value={'no.such.host.com': 'bar.com:1234'}))
    def test_no_nodeinfo_found(self):
        """Test the exit code when no appropriate nodeinfo endpoint is found.
        """
        result = self.runner.invoke(self.met_cli,
                                    ['--outdir', '/tmp', '--cell', 'foo',
                                     'running', 'proid.sampleapp*'])
        self.assertEqual(result.exit_code, -1)

    def test_instance_to_host(self):
        """Test that the message processing func returns True no matter what.
        """
        self.assertTrue(self.met_mod._instance_to_host({'foo': 'bar'}))
        self.assertTrue(self.met_mod._instance_to_host(
            dict(name='foo', host='bar'), {}))

    def test_instance_to_host_uniq(self):
        """Test that the message processing func returns True no matter what.
        """
        self.assertTrue(self.met_mod._instance_to_host_uniq({}))
        self.assertTrue(self.met_mod._instance_to_host_uniq(
            {'event': {'uniqueid': 'foo'}}, uniq='bar'))
        self.assertTrue(self.met_mod._instance_to_host_uniq(
            {'event': {'uniqueid': 'foo',
                       'instanceid': 'bar',
                       'source': 'foobar'}}, {},
            uniq='foo'))


if __name__ == '__main__':
    unittest.main()
