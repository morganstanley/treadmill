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

    def setUp(self):
        self.tm_env = mock.Mock(
            cell='testcell',
            zkurl='zookeeper://foo@foo:123',
            apps_dir='apps',
            root='/var/tmp/treadmill',
        )

    @mock.patch('treadmill.appcfg.features.warpgate.WarpgateFeature.'
                '_get_warpgate_config', mock.Mock(
                    return_value=(['somehost:1234'], 'foo')
                ))
    @mock.patch('treadmill.subproc.resolve', mock.Mock(return_value='tm'))
    def test_warpgate_configure(self):
        """Test warpgate feature configure.
        """
        feature_mod = features.get_feature('warpgate')(self.tm_env)

        self.assertTrue(
            feature_mod.applies(
                manifest={
                    'features': ['warpgate'],
                    'proid': 'foo',
                    'tickets': ['foo@realm'],
                    'environ': [
                        {'name': 'WARPGATE_POLICY', 'value': 'foo'},
                    ],
                },
                runtime='linux'
            )
        )

        self.assertFalse(
            feature_mod.applies(
                manifest={
                    'features': ['warpgate'],
                    'proid': 'foo',
                    'tickets': ['foo@realm'],
                    'environ': [
                        {'name': 'WARPGATE_POLICY', 'value': 'foo'},
                    ],
                },
                runtime='notlinux'
            ),
            'Must use "linux" runtime'
        )
        self.assertFalse(
            feature_mod.applies(
                manifest={
                    'features': ['warpgate'],
                    'proid': 'foo',
                    'tickets': [],
                    'environ': [
                        {'name': 'WARPGATE_POLICY', 'value': 'foo'},
                    ],
                },
                runtime='linux'
            ),
            'Must have some tickets'
        )
        self.assertFalse(
            feature_mod.applies(
                manifest={
                    'features': ['warpgate'],
                    'proid': 'foo',
                    'tickets': ['foo@realm'],
                    'environ': [],
                },
                runtime='linux'
            ),
            'Must have env variable WARPGATE_POLICY'
        )

    @mock.patch('treadmill.appcfg.features.warpgate.WarpgateFeature.'
                '_get_warpgate_config', mock.Mock(
                    return_value=(['somehost:1234'], 'foo')
                ))
    @mock.patch('treadmill.subproc.resolve', mock.Mock(return_value='tm'))
    def test_warpgate_feature(self):
        """Test warpgate feature.
        """
        manifest = {
            'services': [],
            'system_services': [],
            'features': ['warpgate'],
            'proid': 'foo',
            'environ': [
                {'name': 'WARPGATE_POLICY', 'value': 'foo'},
            ],
            'tickets': ['foo@realm'],
        }

        self.assertTrue(features.feature_exists('warpgate'))
        feature_mod = features.get_feature('warpgate')(self.tm_env)

        feature_mod.configure(manifest)
        self.assertEqual(len(manifest['services']), 1)
        self.assertEqual(manifest['services'][0]['name'], 'warpgate')
        self.assertTrue(manifest['services'][0]['root'])
        self.assertEqual(
            manifest['services'][0],
            {
                'command': (
                    'exec $TREADMILL/bin/treadmill sproc'
                    ' --logging-conf daemon_container.json'
                    ' warpgate'
                    ' --policy-servers somehost:1234'
                    ' --policy foo'
                    ' --service-principal foo'
                    ' --tun-dev eth0'
                    ' --tun-addr ${TREADMILL_CONTAINER_IP}'
                ),
                'config': None,
                'downed': False,
                'environ': [
                    {
                        'name': 'KRB5CCNAME',
                        'value': 'FILE:/var/spool/tickets/foo@realm'
                    }
                ],
                'name': 'warpgate',
                'proid': 'root',
                'restart': {
                    'interval': 60,
                    'limit': 5
                },
                'root': True,
                'trace': False
            }
        )


if __name__ == '__main__':
    unittest.main()
