"""Tests for treadmill.rest.limit"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import time
import unittest

import flask
import flask_restplus as restplus
from six.moves import http_client

from treadmill.rest import limit


class LimitTest(unittest.TestCase):
    """Test for treadmill.rest.limit"""

    def setUp(self):
        """Initialize the app with the corresponding limit logic."""
        blueprint = flask.Blueprint('v1', __name__)
        self.api = restplus.Api(blueprint)

        self.app = flask.Flask(__name__)
        self.app.testing = True
        self.app.register_blueprint(blueprint)

    def test_wrap(self):
        """Test rule based request rate control."""
        namespace = self.api.namespace(
            'rrc', description='Request Rate Control REST API Test',
        )

        @namespace.route('/foo')
        class _Foo(restplus.Resource):
            """Request rate control resource example"""

            def get(self):
                """Get resource implement"""
                return ''

        @namespace.route('/bar')
        class _Bar(restplus.Resource):
            """Request rate control resource example"""

            def get(self):
                """Get resource implement"""
                return ''

        self.app = limit.wrap(self.app, '1/second')
        client = self.app.test_client()

        cases = (
            ('/rrc/foo', http_client.OK, 0),
            ('/rrc/foo', http_client.TOO_MANY_REQUESTS, 0),
            ('/rrc/foo', http_client.OK, 1),
            ('/rrc/bar', http_client.TOO_MANY_REQUESTS, 0),
        )
        for (url, expected, seconds) in cases:
            time.sleep(seconds)
            response = client.get(url)
            self.assertEqual(response.status_code, expected)


if __name__ == '__main__':
    unittest.main()
