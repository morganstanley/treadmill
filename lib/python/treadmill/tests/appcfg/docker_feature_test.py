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

    @mock.patch('treadmill.nodedata.get', specs_set=True)
    def test__get_tls_conf(self, mock_nodedata_get):
        """Test getting list of registries
        """
        # pylint: disable=protected-access

        mock_nodedata_get.return_value = {
            'tls_certs': {
                'ca_cert': 'foo',
                'host_cert': 'bar',
                'host_key': 'baz',
            }
        }
        mock_env = mock.Mock()

        res = docker_feature._get_tls_conf(mock_env)

        self.assertEqual(
            res,
            {
                'ca_cert': 'foo',
                'host_cert': 'bar',
                'host_key': 'baz',
            }
        )

        mock_nodedata_get.return_value = {
            'tls_certs': {}
        }

        res = docker_feature._get_tls_conf(mock_env)

        self.assertEqual(
            res,
            {
                'ca_cert': '',
                'host_cert': '',
                'host_key': '',
            }
        )

    @mock.patch('treadmill.appcfg.features.docker.socket.getfqdn',
                specs_set=True)
    @mock.patch('treadmill.nodedata.get', specs_set=True)
    def test__get_docker_registry(self, mock_nodedata_get, mock_fqdn):
        """Test getting list of registries
        """
        # pylint: disable=protected-access

        mock_nodedata_get.return_value = {
            'docker_registries': {
                'dev': ['foo', 'bar:1234'],
                'prod': ['mshub.ms.com'],
            }
        }
        mock_fqdn.side_effect = [
            'somehost1',
            'somehost2',
            'somehost3',
        ]
        mock_env = mock.Mock()

        dev_res = docker_feature._get_docker_registry(mock_env, 'dev')
        self.assertEqual(
            list(dev_res),
            [
                'somehost1',
                'somehost2:1234'
            ]
        )
        mock_fqdn.assert_has_calls([
            mock.call('foo'),
            mock.call('bar'),
        ])
        mock_fqdn.reset_mock()

        prod_res = docker_feature._get_docker_registry(mock_env, 'prod')
        self.assertEqual(
            list(prod_res),
            [
                'somehost3',
            ]
        )
        mock_fqdn.assert_has_calls([
            mock.call('mshub.ms.com'),
        ])
        mock_fqdn.reset_mock()

        foo_res = docker_feature._get_docker_registry(mock_env, 'foo')
        self.assertEqual(
            list(foo_res),
            []
        )
        mock_fqdn.assert_has_calls([])

        # Compatibitily mode test
        mock_nodedata_get.return_value = {
            'docker_registries': ['foo', 'bar:1234'],
        }
        mock_fqdn.side_effect = [
            'somehost1',
            'somehost2',
        ]

        dev_res = docker_feature._get_docker_registry(mock_env, 'dev')
        self.assertEqual(
            list(dev_res),
            [
                'somehost1',
                'somehost2:1234'
            ]
        )

        mock_fqdn.side_effect = [
            'somehost1',
            'somehost2',
        ]
        prod_res = docker_feature._get_docker_registry(mock_env, 'prod')
        self.assertEqual(
            list(prod_res),
            [
                'somehost1',
                'somehost2:1234'
            ]
        )

    @mock.patch('treadmill.subproc.resolve', mock.Mock(return_value='tm'))
    @mock.patch('treadmill.utils.get_ulimit', mock.Mock(return_value=(0, 0)))
    @mock.patch('treadmill.appcfg.features.docker._get_tls_conf',
                mock.Mock(return_value=dict(
                    ca_cert='/ca.pem',
                    host_cert='/host.pem',
                    host_key='/host.key'
                )))
    @mock.patch('treadmill.appcfg.features.docker._get_docker_registry',
                mock.Mock(return_value=iter(['foo:5050', 'bar:5050'])))
    def test_docker_feature(self):
        """test apply dockerd feature
        """
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

        self.assertTrue(features.feature_exists('docker'))

        feature_mod = features.get_feature('docker')(tm_env)
        feature_mod.configure(manifest)
        self.assertEqual(len(manifest['services']), 2)
        self.assertEqual(manifest['services'][0]['name'], 'dockerd')
        self.assertTrue(manifest['services'][0]['root'])
        self.assertEqual(
            manifest['services'][0]['command'],
            (
                'exec tm'
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
                ' --tlsverify'
                ' --tlscacert=/ca.pem'
                ' --tlscert=/host.pem'
                ' --tlskey=/host.key'
                ' --add-registry foo:5050'
                ' --add-registry bar:5050'
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
