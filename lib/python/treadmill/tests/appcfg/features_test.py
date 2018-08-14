"""Unit test for treadmill.appcfg.manifest.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

from treadmill.appcfg import manifest


class AppCfgFeaturesTest(unittest.TestCase):
    """Tests for teadmill.appcfg.features.
    """

    def test_add_missing(self):
        """Tests adding a not existing feature.
        """
        mf = {
            'services': [],
            'system_services': [],
            'features': ['no_such_feature']
        }

        tm_env = mock.Mock(
            cell='testcell',
            zkurl='zookeeper://foo@foo:123',
            apps_dir='apps',
        )

        with self.assertRaises(Exception, msg='foo') as cm:
            manifest.add_manifest_features(mf, 'linux', tm_env)

        self.assertIn('Unsupported feature', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
