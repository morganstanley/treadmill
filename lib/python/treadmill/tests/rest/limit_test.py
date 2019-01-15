"""Tests for treadmill.rest.limit"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import time
import unittest

import flask
import flask_restplus as restplus
import mock
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

        na = self.api.namespace(
            'na', description='Request Rate Control REST API Test',
        )

        @na.route('/foo')
        class _Foo(restplus.Resource):
            """Request rate control resource example"""

            def get(self):
                """Get resource implement"""
                return ''

        @na.route('/bar')
        class _Bar(restplus.Resource):
            """Request rate control resource example"""

            def get(self):
                """Get resource implement"""
                return ''

        nb = self.api.namespace(
            'nb', description='Request Rate Control REST API Test',
        )

        @nb.route('/baz')
        class _Baz(restplus.Resource):
            """Request rate control resource example"""

            def get(self):
                """Get resource implement"""
                return ''

    def test_wrap(self):
        """Test rule based request rate control."""
        rate_limits = [
            {'_global': '1/second'},
            {'limit_test': '1/second'},
        ]
        for rate_limit in rate_limits:
            self.setUp()

            self.app = limit.wrap(self.app, rate_limit)
            client = self.app.test_client()

            now = time.time()
            cases = (
                ('/na/foo', http_client.OK, now),
                ('/na/foo', http_client.TOO_MANY_REQUESTS, now),
                ('/na/foo', http_client.OK, now + 1),
                ('/na/bar', http_client.TOO_MANY_REQUESTS, now + 1),
                ('/nb/baz', http_client.TOO_MANY_REQUESTS, now + 1),
                ('/nb/baz', http_client.OK, now + 2),
            )
            with mock.patch('time.time') as mock_time:
                for (url, expected, when) in cases:
                    mock_time.return_value = when
                    response = client.get(url)
                    self.assertEqual(response.status_code, expected)


if __name__ == '__main__':
    unittest.main()
