"""Unit test for treadmill.runtime.linux._manifest.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows   # pylint: disable=W0611

from treadmill.runtime.linux import _manifest as app_manifest


class Docker2RuntimeManifestTest(unittest.TestCase):
    """Tests for treadmill.runtime.linux._manifest."""

    def setUp(self):
        self.tm_env = mock.Mock(
            root='/var/lib/treadmill/app/approot',
            cell='testcell',
            zkurl='zookeeper://foo@foo:123',
            apps_dir='apps',
        )

    def tearDown(self):
        pass

    @mock.patch(
        'treadmill.subproc.resolve', mock.Mock(return_value='/treadmill-bind')
    )
    def test__get_docker_run_cmd(self):
        """Test docker command parsing/generation.
        """
        # pylint: disable=protected-access

        cmd = app_manifest._get_docker_run_cmd(
            name='foo',
            image='testwt2'
        )
        self.assertEqual(
            cmd,
            (
                'exec $TREADMILL/bin/treadmill sproc docker'
                ' --name foo'
                ' --envdirs /env,/docker/env,/services/foo/env'
                ' --volume /var/log:/var/log:rw'
                ' --volume /var/spool:/var/spool:rw'
                ' --volume /var/tmp:/var/tmp:rw'
                ' --volume /docker/etc/hosts:/etc/hosts:ro'
                ' --volume /env:/env:ro'
                ' --volume /treadmill-bind:/opt/treadmill-bind:ro'
                ' --image testwt2'
            )
        )

        cmd = app_manifest._get_docker_run_cmd(
            name='foo',
            image='testwt2',
            commands='/bin/sh -c "echo $foo $bar"',
        )
        self.assertEqual(
            cmd,
            (
                'exec $TREADMILL/bin/treadmill sproc docker'
                ' --name foo'
                ' --envdirs /env,/docker/env,/services/foo/env'
                ' --volume /var/log:/var/log:rw'
                ' --volume /var/spool:/var/spool:rw'
                ' --volume /var/tmp:/var/tmp:rw'
                ' --volume /docker/etc/hosts:/etc/hosts:ro'
                ' --volume /env:/env:ro'
                ' --volume /treadmill-bind:/opt/treadmill-bind:ro'
                ' --image testwt2'
                ' --'
                ' /bin/sh -c \'echo $foo $bar\''
            )
        )

        cmd = app_manifest._get_docker_run_cmd(
            name='bar',
            image='testwt2',
            commands='entry_point.sh',
            use_shell=False
        )
        self.assertEqual(
            cmd,
            (
                'exec $TREADMILL/bin/treadmill sproc docker'
                ' --name bar'
                ' --envdirs /env,/docker/env,/services/bar/env'
                ' --volume /var/log:/var/log:rw'
                ' --volume /var/spool:/var/spool:rw'
                ' --volume /var/tmp:/var/tmp:rw'
                ' --volume /docker/etc/hosts:/etc/hosts:ro'
                ' --volume /env:/env:ro'
                ' --volume /treadmill-bind:/opt/treadmill-bind:ro'
                ' --image testwt2'
                ' --entrypoint entry_point.sh'
            )
        )


if __name__ == '__main__':
    unittest.main()
