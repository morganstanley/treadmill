"""Unit test for treadmill.appcfg.features.warpgate
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill.appcfg import features


class AppCfgWarpgateFeatureTest(unittest.TestCase):
    """Test for warpgate feature
    """

    @mock.patch('treadmill.subproc.resolve', mock.Mock(return_value='tm'))
    def test_warpgate_feature(self):
        """Test warpgate feature.
        """
        manifest = {
            'services': [],
            'system_services': [],
            'features': ['warpgate'],
            'proid': 'foo',
            'environ': [],
        }

        tm_env = mock.Mock(
            cell='testcell',
            zkurl='zookeeper://foo@foo:123',
            apps_dir='apps',
            root='/var/tmp/treadmill',
        )

        self.assertTrue(features.feature_exists('warpgate'))

        feature_mod = features.get_feature('warpgate')(tm_env)
        feature_mod.configure(manifest)
        self.assertEqual(len(manifest['system_services']), 1)
        self.assertEqual(manifest['system_services'][0]['name'], 'warpgate')
        self.assertTrue(manifest['system_services'][0]['root'])
        self.assertEqual(
            manifest['system_services'][0]['command'],
            'exec $TREADMILL/bin/treadmill sproc warpgate'
        )


if __name__ == '__main__':
    unittest.main()
