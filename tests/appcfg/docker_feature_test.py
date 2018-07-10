"""Unit test for treadmill.appcfg.features.docker
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

from treadmill.appcfg import features


class AppCfgDockerFeatureTest(unittest.TestCase):
    """Test for docker feature
    """

    @mock.patch('treadmill.appcfg.features.docker._get_user_uid_gid',
                mock.Mock(return_value=(1, 1)))
    @mock.patch('treadmill.subproc.resolve', mock.Mock(return_value='foo'))
    @mock.patch('treadmill.appcfg.features.docker._get_docker_registry',
                mock.Mock(return_value='foo:5050'))
    def test_docker_feature(self):
        """test apply dockerd feature
        """
        manifest = {
            'services': [],
            'system_services': [],
            'features': ['docker'],
            'proid': 'foo',
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
        self.assertEqual(len(manifest['services']), 1)
        self.assertEqual(manifest['services'][0]['name'], 'dockerd')
        self.assertTrue(manifest['services'][0]['root'])


if __name__ == '__main__':
    unittest.main()
