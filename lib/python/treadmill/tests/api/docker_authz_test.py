"""Unit test for treadmill.docker_authz
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill.api import docker_authz
from treadmill.api.docker_authz import plugins


class DockerAuthzPluginTest(unittest.TestCase):
    """Tests for treadmill.api.docker_authz plugin"""

    def test_exec_user(self):
        """test user of docker exec
        """
        plugin = plugins.DockerExecUserPlugin()

        # no user name
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/bar/exec',
            {},
        )
        self.assertTrue(allow)

        # correct user name
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/bar/exec',
            {'User': '123:456'},
        )
        self.assertTrue(allow)

    def test_run_user(self):
        """Test check user in docker run
        """
        plugin = plugins.DockerRunUserPlugin()

        # pylint: disable=protected-access
        # no user name
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'Image': 'foo'
            },
        )
        self.assertTrue(allow)

        # correct user name
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'User': '123:456',
                'Image': 'foo'
            },
        )
        self.assertTrue(allow)

    def test_run_privilege(self):
        """test run docker container with privilege
        """
        plugin = plugins.DockerRunPrivilegePlugin()
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'Image': 'foo',
                'HostConfig': {
                    'Privileged': False
                }
            },
        )
        self.assertTrue(allow)

        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'Image': 'foo',
                'HostConfig': {
                    'Privileged': True
                }
            },
        )
        self.assertFalse(allow)

        plugin = plugins.DockerRunPrivilegePlugin(privileged=True)

        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'Image': 'foo',
                'HostConfig': {
                    'Privileged': True
                }
            },
        )
        self.assertTrue(allow)

    def test_run_cap(self):
        """test run docker container with additional capabilities
        """
        plugin = plugins.DockerRunPrivilegePlugin()
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'Image': 'foo',
                'HostConfig': {
                    'CapAdd': None
                }
            },
        )
        self.assertTrue(allow)

        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'Image': 'foo',
                'HostConfig': {
                    'CapAdd': ['SYS_ADMIN']
                }
            },
        )
        self.assertFalse(allow)

        plugin = plugins.DockerRunPrivilegePlugin(caps=['SYS_ADMIN'])
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'Image': 'foo',
                'HostConfig': {
                    'CapAdd': ['SYS_ADMIN']
                }
            },
        )
        self.assertTrue(allow)

        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'Image': 'foo',
                'HostConfig': {
                    'CapAdd': ['SYS_ADMIN', 'NET_ADMIN']
                }
            },
        )
        self.assertFalse(allow)


class DockerAuthzAPITest(unittest.TestCase):
    """Test Docker Authz API
    """

    def test_authzreq(self):
        """Test authzreq
        """
        _api = docker_authz.API()

        # {"User": "123:456", "Image": "foo"}
        body = 'eyJVc2VyIjogIjEyMzo0NTYiLCAiSW1hZ2UiOiAiZm9vIn0K'
        data = {
            'RequestBody': body,
            'RequestMethod': 'POST',
            'RequestUri': '/v1.26/containers/create',
        }
        (allow, msg) = _api.authzreq(data)

        self.assertEqual(msg, 'Allowed')
        self.assertTrue(allow)

        # {"User": "foo", "Image": "foo"}
        body = 'eyJVc2VyIjogImZvbyIsICJJbWFnZSI6ICJmb28ifQo='
        data = {
            'RequestBody': body,
            'RequestMethod': 'POST',
            'RequestUri': '/v1.26/containers/create',
        }
        (allow, msg) = _api.authzreq(data)
        self.assertTrue(allow)


if __name__ == '__main__':
    unittest.main()
