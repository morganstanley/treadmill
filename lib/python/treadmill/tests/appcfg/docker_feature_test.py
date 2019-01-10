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


class AppCfgDockerFeatureTest(unittest.TestCase):
    """Test for docker feature
    """

    @mock.patch('treadmill.subproc.resolve', mock.Mock(return_value='tm'))
    @mock.patch('treadmill.utils.get_ulimit', mock.Mock(return_value=(0, 0)))
    @mock.patch('treadmill.appcfg.features.docker._get_docker_registry',
                mock.Mock(return_value=iter(['foo:5050', 'bar:5050'])))
    def test_docker_feature(self):
        """test apply dockerd feature
        """
        manifest = {
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

        self.assertTrue(features.feature_exists('docker'))

        feature_mod = features.get_feature('docker')(tm_env)
        feature_mod.configure(manifest)
        self.assertEqual(len(manifest['services']), 2)
        self.assertEqual(manifest['services'][0]['name'], 'dockerd')
        self.assertTrue(manifest['services'][0]['root'])
        self.assertEqual(
            manifest['services'][0]['command'],
            ('exec tm'
             ' -H tcp://127.0.0.1:2375'
             ' --authorization-plugin=authz'
             ' --add-runtime docker-runc=tm --default-runtime=docker-runc'
             ' --exec-opt native.cgroupdriver=cgroupfs --bridge=none'
             ' --ip-forward=false --ip-masq=false --iptables=false'
             ' --cgroup-parent=docker --block-registry="*"'
             ' --default-ulimit core=0:0'
             ' --default-ulimit data=0:0'
             ' --default-ulimit fsize=0:0'
             ' --default-ulimit nproc=0:0'
             ' --default-ulimit nofile=0:0'
             ' --default-ulimit rss=0:0'
             ' --default-ulimit stack=0:0'
             ' --insecure-registry foo:5050 --add-registry foo:5050'
             ' --insecure-registry bar:5050 --add-registry bar:5050')
        )
        self.assertEqual(manifest['services'][1]['name'], 'docker-auth')
        self.assertTrue(manifest['services'][1]['root'])
        self.assertIn(
            {'name': 'DOCKER_HOST', 'value': 'tcp://127.0.0.1:2375'},
            manifest['environ']
        )


if __name__ == '__main__':
    unittest.main()
