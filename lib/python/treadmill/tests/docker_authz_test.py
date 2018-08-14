"""Unit test for treadmill.docker_authz
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest


from treadmill.docker_authz import plugins


class DockerAuthzTest(unittest.TestCase):
    """Tests for treadmill.docker_authz"""

    def test_inspect_user(self):
        """test get user from image
        """
        plugin = plugins.DockerInspectUserPlugin()

        (status, msg) = plugin.run_res(
            'GET',
            '/v1.26/images/foo/json',
            {},
            {'Config': {'User': 'user1'}}
        )

        self.assertEqual(status, 200)
        # pylint: disable=protected-access
        self.assertEqual(
            plugins._IMAGE_USER,
            {'foo': 'user1'}
        )

    def test_exec_user(self):
        """test user of docker exec
        """
        users = [(123, 456)]
        plugin = plugins.DockerExecUserPlugin(users)

        # no user name
        (status, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/bar/exec',
            {},
        )
        self.assertEqual(status, 403)

        # wrong user name
        (status, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/bar/exec',
            {'User': 'user'},
        )
        self.assertEqual(status, 403)

        # correct user name
        (status, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/bar/exec',
            {'User': '123:456'},
        )
        self.assertEqual(status, 200)

    def test_run_user(self):
        """Test check user in docker run
        """
        users = [(123, 456)]
        plugin = plugins.DockerRunUserPlugin(users)

        # pylint: disable=protected-access
        plugins._IMAGE_USER = {}
        # no user name
        (status, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'Image': 'foo'
            },
        )
        self.assertEqual(status, 403)

        # wrong user name
        (status, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'User': 'whoami',
                'Image': 'foo'
            },
        )
        self.assertEqual(status, 403)

        # correct user name
        (status, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'User': '123:456',
                'Image': 'foo'
            },
        )
        self.assertEqual(status, 200)

        plugins._IMAGE_USER = {'foo': '5:5'}
        (status, msg) = plugin.run_req(
            'POST',
            '/v1.26/containers/create',
            {
                'Image': 'foo'
            },
        )
        self.assertEqual(status, 200)


if __name__ == '__main__':
    unittest.main()
