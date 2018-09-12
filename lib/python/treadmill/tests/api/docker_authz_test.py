"""Unit test for treadmill.docker_authz
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill.api import docker_authz
from treadmill.api.docker_authz import plugins


class DockerAuthzPluginTest(unittest.TestCase):
    """Tests for treadmill.api.docker_authz plugin"""

    def test_inspect_user(self):
        """test get user from image
        """
        plugin = plugins.DockerInspectUserPlugin()

        (allow, msg) = plugin.run_res(
            'GET',
            '/v1.26/images/foo/json',
            {},
            {'Config': {'User': 'user1'}}
        )

        self.assertTrue(allow)
        # pylint: disable=protected-access
        self.assertEqual(
            plugins._IMAGE_USER,
            {'foo': 'user1'}
        )

    def test_exec_user(self):
        """test user of docker exec
        """
        users = [(123, 456)]
        plugin = plugins.DockerExecUserPlugin()

        # no user name
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/bar/exec',
            {},
            users=users
        )
        self.assertFalse(allow)

        # wrong user name
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/bar/exec',
            {'User': 'user'},
            users=users
        )
        self.assertFalse(allow)

        # correct user name
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/bar/exec',
            {'User': '123:456'},
            users=users
        )
        self.assertTrue(allow)

    def test_run_user(self):
        """Test check user in docker run
        """
        users = [(123, 456)]
        plugin = plugins.DockerRunUserPlugin()

        # pylint: disable=protected-access
        plugins._IMAGE_USER = {}
        # no user name
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'Image': 'foo'
            },
            users=users
        )
        self.assertFalse(allow)

        # wrong user name
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'User': 'whoami',
                'Image': 'foo'
            },
            users=users
        )
        self.assertFalse(allow)

        # correct user name
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'User': '123:456',
                'Image': 'foo'
            },
            users=users
        )
        self.assertTrue(allow)

        plugins._IMAGE_USER = {'foo': '5:5'}
        (allow, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'Image': 'foo'
            },
            users=users
        )
        self.assertTrue(allow)


class DockerAuthzAPITest(unittest.TestCase):
    """Test Docker Authz API
    """

    @mock.patch('treadmill.utils.get_uid_gid',
                mock.Mock(return_value=(123, 456)))
    def test_authzreq(self):
        """Test authzreq
        """
        _api = docker_authz.API(users=['foo'])

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
        # get_uid_gid convert name to 123:456
        body = 'eyJVc2VyIjogImZvbyIsICJJbWFnZSI6ICJmb28ifQo='
        data = {
            'RequestBody': body,
            'RequestMethod': 'POST',
            'RequestUri': '/v1.26/containers/create',
        }
        (allow, msg) = _api.authzreq(data)
        self.assertTrue(allow)

    @mock.patch('treadmill.utils.get_uid_gid',
                mock.Mock(side_effect=[(12, 34), (56, 78)]))
    def test_authzreq_fail(self):
        """Test authzreq unauthz
        """
        _api = docker_authz.API(users=['foo'])
        # pylint: disable=protected-access
        self.assertEqual(_api._users, [(12, 34)])

        # {"User": "foo", "Image": "foo"}
        # get_uid_gid convert name to 56:78
        body = 'eyJVc2VyIjogImZvbyIsICJJbWFnZSI6ICJmb28ifQo='
        data = {
            'RequestBody': body,
            'RequestMethod': 'POST',
            'RequestUri': '/v1.26/containers/create',
        }
        (allow, msg) = _api.authzreq(data)
        self.assertFalse(allow)

    @mock.patch('treadmill.utils.get_uid_gid',
                mock.Mock(return_value=(123, 456)))
    def test_authzres(self):
        """Test different API can handle image user
        """
        _api1 = docker_authz.API(users=['foo'])
        _api2 = docker_authz.API(users=['foo'])

        # {"Config": {"User": "user1"}}
        body = 'eyJDb25maWciOiB7IlVzZXIiOiAidXNlcjEifX0K'
        data = {
            'RequestMethod': 'GET',
            'RequestUri': '/v1.26/images/foo/json',
            'RequestBody': 'e30K',  # for {}
            'ResponseBody': body,
        }
        (allow, msg) = _api1.authzres(data)
        self.assertTrue(allow)

        # {"User": "", "Image": "foo"}
        body = 'eyJVc2VyIjogIiIsICJJbWFnZSI6ICJmb28ifQo='
        data = {
            'RequestBody': body,
            'RequestMethod': 'POST',
            'RequestUri': '/v1.26/containers/create',
        }
        (allow, msg) = _api2.authzreq(data)
        self.assertTrue(allow)


if __name__ == '__main__':
    unittest.main()
