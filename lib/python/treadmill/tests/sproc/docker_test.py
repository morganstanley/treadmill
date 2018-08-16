"""Unit test for treadmill.sproc.appmonitor.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import docker
import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill.sproc import docker as sproc_docker


class DockerTest(unittest.TestCase):
    """Test treadmill sproc docker
    """

    @mock.patch('treadmill.sproc.docker._get_image_user',
                mock.Mock(return_value='user'))
    @mock.patch('docker.models.containers.ContainerCollection.get')
    @mock.patch('docker.models.containers.ContainerCollection.create')
    def test_create_container_with_user(self, create_call_mock, get_call_mock):
        """Test _create_container with user in docker image
        """
        # pylint: disable=protected-access

        client = docker.from_env()

        sproc_docker._create_container(
            client, 'bar', 'foo', mock.Mock(), None, ['cmd']
        )

        get_call_mock.assert_called_with('bar')
        create_call_mock.assert_called_with(
            command=['cmd'], detach=True, entrypoint=None, image='foo',
            ipc_mode='host', name='bar', network_mode='host',
            pid_mode='host', stdin_open=True, tty=True
        )

    @mock.patch('treadmill.sproc.docker._get_image_user',
                mock.Mock(return_value=None))
    @mock.patch('docker.models.containers.ContainerCollection.get',
                mock.Mock())
    @mock.patch('os.getuid', mock.Mock(return_value=1))
    @mock.patch('os.getgid', mock.Mock(return_value=2))
    @mock.patch('docker.models.containers.ContainerCollection.create')
    def test_create_container_no_user(self, create_call_mock):
        """Test _create_container without user in docker image
        """
        # pylint: disable=protected-access

        client = docker.from_env()

        sproc_docker._create_container(
            client, 'bar', 'foo', mock.Mock(), ['entrypoint'], ['cmd']
        )

        create_call_mock.assert_called_with(
            command=['cmd'], detach=True, entrypoint=['entrypoint'],
            image='foo', ipc_mode='host', name='bar', network_mode='host',
            pid_mode='host', stdin_open=True, tty=True, user='1:2'
        )


if __name__ == '__main__':
    unittest.main()
