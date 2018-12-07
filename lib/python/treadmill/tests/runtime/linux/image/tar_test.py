"""Tests for treadmill.runtime.linux.image.tar.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import tempfile
import unittest
import io

import mock
import pkg_resources

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows   # pylint: disable=W0611

import treadmill
import treadmill.services
import treadmill.subproc
import treadmill.rulefile

from treadmill import utils

from treadmill.runtime.linux.image import tar


def _test_data(name):
    data_path = os.path.join('data', name)
    with pkg_resources.resource_stream(__name__, data_path) as f:
        return f.read()


class TarImageTest(unittest.TestCase):
    """Tests for treadmill.runtime.linux.image.tar."""

    def setUp(self):
        # Access protected module _base_service
        # pylint: disable=W0212
        self.container_dir = tempfile.mkdtemp()
        self.root = tempfile.mkdtemp(dir=self.container_dir)
        self.tmp_dir = tempfile.mkdtemp()
        self.images_dir = tempfile.mkdtemp()
        self.tm_env = mock.Mock(
            root=self.root,
            images_dir=self.images_dir,
            svc_cgroup=mock.Mock(
                spec_set=treadmill.services._base_service.ResourceService,
            ),
            svc_localdisk=mock.Mock(
                spec_set=treadmill.services._base_service.ResourceService,
            ),
            svc_network=mock.Mock(
                spec_set=treadmill.services._base_service.ResourceService,
            ),
            rules=mock.Mock(
                spec_set=treadmill.rulefile.RuleMgr,
            ),
        )
        self.app = utils.to_obj(
            {
                'type': 'native',
                'proid': 'myproid',
                'name': 'myproid.test#0',
                'uniqueid': 'ID1234',
                'environment': 'dev',
                'disk': '100G',
                'endpoints': [
                    {
                        'name': 'ssh',
                        'port': 47299,
                        'proto': 'tcp',
                        'real_port': 47299,
                        'type': 'infra'
                    }
                ],
                'shared_network': False,
                'ephemeral_ports': {
                    'tcp': 0,
                    'udp': 0
                }
            }
        )

    def tearDown(self):
        if self.container_dir and os.path.isdir(self.container_dir):
            shutil.rmtree(self.container_dir)

        if self.images_dir and os.path.isdir(self.images_dir):
            shutil.rmtree(self.images_dir)

        if self.tmp_dir and os.path.isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    @mock.patch('treadmill.runtime.linux.image.native.NativeImage',
                mock.Mock())
    def test_get_tar_sha256_unpack(self):
        """Validates getting a test tar file with a sha256 hash_code."""
        with io.open(os.path.join(self.tmp_dir, 'sleep.tar'), 'wb') as f:
            f.write(_test_data('sleep.tar'))

        repo = tar.TarImageRepository(self.tm_env)
        img = repo.get(
            'file://{0}/sleep.tar?sha256={1}'.format(
                self.tmp_dir,
                '5a0f99c73b03f7f17a9e03b20816c2931784d5e1fc574eb2d0dece57'
                'f509e520'
            )
        )

        self.assertIsNotNone(img)
        img.unpack(self.container_dir, self.root, self.app, {})

    def test_get_tar__invalid_sha256(self):
        """Validates getting a test tar file with an invalid sha256 hash_code.
        """
        with io.open(os.path.join(self.tmp_dir, 'sleep.tar'), 'wb') as f:
            f.write(_test_data('sleep.tar'))

        repo = tar.TarImageRepository(self.tm_env)

        with self.assertRaises(Exception):
            repo.get(
                'file://{0}/sleep.tar?sha256={1}'.format(
                    self.tmp_dir,
                    'this_is_an_invalid_sha256'
                )
            )


if __name__ == '__main__':
    unittest.main()
