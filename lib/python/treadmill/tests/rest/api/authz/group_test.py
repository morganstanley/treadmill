"""Group based authorization REST api tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import unittest

import flask
import flask_restplus as restplus
import mock

from six.moves import http_client

from treadmill import webutils
from treadmill.rest.api.authz import group


class GroupTest(unittest.TestCase):
    """Test the logic corresponding to the group based authorization."""

    def setUp(self):
        """Initialize the app with the corresponding logic."""
        self.app = flask.Flask(__name__)
        self.app.testing = True
        self.impl = mock.Mock()

        api = restplus.Api(self.app)
        cors = webutils.cors(
            origin='*',
            content_type='application/json',
            credentials=False,
        )
        group.init(api, cors, self.impl)

        self.client = self.app.test_client()

    def test_authorization(self):
        """Test Unix group based authorization"""

        # successful authorization
        self.impl.authorize.return_value = (True, [])
        resp = self.client.post(
            '/foo/create/bar',
            data=json.dumps({}),
            content_type='application/json'
        )
        self.impl.authorize.assert_called_once_with('foo', 'create', 'bar', {})
        self.assertEqual(resp.status_code, http_client.OK)
        self.assertTrue(json.loads(resp.data.decode())['auth'])

        # permissoin denied
        self.impl.reset_mock()
        self.impl.authorize.return_value = (False, ["Denied"])
        resp = self.client.post(
            '/foo/update/bar',
            data=json.dumps({'pk': 123}),
            content_type='application/json'
        )
        self.impl.authorize.assert_called_once_with(
            'foo', 'update', 'bar', {'pk': 123},
        )
        self.assertEqual(resp.status_code, http_client.OK)
        self.assertFalse(json.loads(resp.data.decode())['auth'])

        # unexpected internal error
        self.impl.reset_mock()
        self.impl.authorize.side_effect = TypeError("oops")
        resp = self.client.post(
            '/foo/delete/bar',
            data=json.dumps({'pk': 123, 'metadata': 'extra'}),
            content_type='application/json'
        )
        self.impl.authorize.assert_called_once_with(
            'foo', 'delete', 'bar', {'pk': 123, 'metadata': 'extra'},
        )
        self.assertEqual(resp.status_code, http_client.INTERNAL_SERVER_ERROR)
        self.assertFalse(json.loads(resp.data.decode())['auth'])


if __name__ == '__main__':
    unittest.main()
