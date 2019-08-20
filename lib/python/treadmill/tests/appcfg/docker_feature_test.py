"""Unit test for treadmill.appcfg.features.docker
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill.appcfg import features
from treadmill.appcfg.features import docker as docker_feature


class AppCfgDockerFeatureTest(unittest.TestCase):
    """Test for docker feature
    """

    def test_featrue_exist(self):
        """test docker feature exists
        """
        self.assertTrue(features.feature_exists('docker'))

    @mock.patch('treadmill.subproc.resolve', mock.Mock(return_value='tm'))
    @mock.patch('treadmill.utils.get_ulimit', mock.Mock(return_value=(0, 0)))
    @mock.patch('treadmill.nodedata.get', mock.Mock())
    @mock.patch('treadmill.dockerutils.get_conf')
    def test_docker_feature(self, mock_getconf):
        """test apply dockerd feature
        """
        mock_getconf.return_value = {
            'daemon_conf': {
                'signature-verification': False,
            },
            'registries': [
                {
                    'host': 'hub-dev',
                    'insecure': True,
                },
                {
                    'host': 'hub-dev2',
                    'insecure': False,
                    'ca_cert': '/etc/foo.crt',
                }
            ]
        }
        manifest = {
            'environment': 'dev',
            'services': [],
            'system_services': [],
            'features': ['docker'],
            'proid': 'foo',
            'environ': [],
        }
        tm_env = mock.Mock(
            cell='testcell',
            zkurl='zookeeper://foo@foo:123',
            apps_dir='apps',
            root='/var/tmp/treadmill',
        )
        feature_mod = docker_feature.DockerdFeature(tm_env)
        feature_mod.configure(manifest)

        self.assertEqual(len(manifest['services']), 2)
        self.assertEqual(manifest['services'][0]['name'], 'dockerd')
        self.assertTrue(manifest['services'][0]['root'])
        self.assertEqual(
            manifest['services'][0]['command'],
            (
                'exec tm'
                ' --default-ulimit core=0:0'
                ' --default-ulimit data=0:0'
                ' --default-ulimit fsize=0:0'
                ' --default-ulimit nofile=0:0'
                ' --default-ulimit nproc=0:0'
                ' --default-ulimit rss=0:0'
                ' --default-ulimit stack=0:0'
                ' --block-registry="*"'
                ' --add-registry hub-dev'
                ' --insecure-registry hub-dev'
                ' --add-registry hub-dev2'
            )
        )
        self.assertEqual(manifest['services'][1]['name'], 'docker-auth')
        self.assertTrue(manifest['services'][1]['root'])
        self.assertIn(
            {'name': 'DOCKER_HOST', 'value': 'tcp://127.0.0.1:2375'},
            manifest['environ']
        )


if __name__ == '__main__':
    unittest.main()
