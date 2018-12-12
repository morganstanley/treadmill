"""Cgroup Stats REST api tests.
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
from treadmill.rest import error_handlers
from treadmill.rest.api import cgroup


class CgroupTest(unittest.TestCase):
    """Test the logic corresponding to the /cgroup namespace."""

    def setUp(self):
        """Initialize the app with the corresponding logic."""
        self.app = flask.Flask(__name__)
        self.app.testing = True

        api = restplus.Api(self.app)
        error_handlers.register(api)

        cors = webutils.cors(origin='*',
                             content_type='application/json',
                             credentials=False)
        self.impl = mock.Mock()

        cgroup.init(api, cors, self.impl)
        self.client = self.app.test_client()

    def assert_response_equal(self, response, expected):
        """Assert response body equals to expected value.
        """
        self.assertEqual(response.status_code, http_client.OK)

        actual = b''.join(response.response)
        self.assertEqual(json.loads(actual.decode()), expected)

    def test_system_slice(self):
        """Test get system.slice cgroup resource"""
        stats = {
            'memory.usage_in_bytes': 1
        }
        self.impl.system.return_value = stats

        response = self.client.get(
            '/cgroup/system',
            content_type='application/json'
        )
        self.assert_response_equal(response, stats)
        self.impl.system.assert_called_once_with('system.slice')

    def test_treadmill(self):
        """Test get Treadmill top level cgroup resource"""
        stats = {
            'cpu.shares': 155
        }
        self.impl.system.return_value = stats

        response = self.client.get(
            '/cgroup/treadmill',
            content_type='application/json'
        )
        self.assert_response_equal(response, stats)
        self.impl.system.assert_called_once_with('treadmill')

    def test_treadmill_all(self):
        """Test get all Treadmill core/apps cgroup resources"""
        stats = {
            'cpu.shares': 155
        }
        self.impl.system.return_value = stats

        response = self.client.get(
            '/cgroup/treadmill/*/',
            content_type='application/json'
        )
        expected = {
            'core': stats,
            'apps': stats,
        }
        self.assert_response_equal(response, expected)
        self.impl.system.assert_has_calls([
            mock.call('treadmill', 'core'),
            mock.call('treadmill', 'apps'),
        ])

    def test_treadmill_core(self):
        """Test get Treadmill aggregated core service cgroup resource"""
        stats = {
            'memory.soft_limit_in_bytes': 12363444224
        }
        self.impl.system.return_value = stats

        response = self.client.get(
            '/cgroup/treadmill/core',
            content_type='application/json'
        )
        self.assert_response_equal(response, stats)
        self.impl.system.assert_called_once_with('treadmill', 'core')

    def test_treadmill_core_service(self):
        """Test get Treadmill core service cgroup resource"""
        stats = {
            'memory.usage_in_bytes': 84454415544
        }
        self.impl.service.return_value = stats

        response = self.client.get(
            '/cgroup/treadmill/core/login_sshd',
            content_type='application/json'
        )
        self.assert_response_equal(response, stats)
        self.impl.service.assert_called_once_with('login_sshd')

    def test_treadmill_core_service_all(self):
        """Test get all Treadmill core service cgroup resources"""
        self.impl.services.return_value = {}

        cases = (
            ('/cgroup/treadmill/core/*/', False),
            ('/cgroup/treadmill/core/*/?detail=true', True),
            ('/cgroup/treadmill/core/*/?detail=false', False),
            ('/cgroup/treadmill/core/*/?detail=1', True),
            ('/cgroup/treadmill/core/*/?detail=0', False),
        )

        for url, detail in cases:
            self.impl.services.reset_mock()
            response = self.client.get(url, content_type='application/json')
            self.assertEqual(response.status_code, http_client.OK)
            self.impl.services.assert_called_once_with(detail=detail)

    def test_treadmill_apps(self):
        """Test get Treadmill aggregated app cgroup resource"""
        stats = {
            'memory.soft_limit_in_bytes': 12363444224
        }
        self.impl.system.return_value = stats

        response = self.client.get(
            '/cgroup/treadmill/apps',
            content_type='application/json'
        )
        self.assert_response_equal(response, stats)
        self.impl.system.assert_called_once_with('treadmill', 'apps')

    def test_treadmill_app(self):
        """Test get Treadmill app cgroup resource"""
        stats = {
            'memory.usage_in_bytes': 84454415544
        }
        self.impl.app.return_value = stats

        response = self.client.get(
            '/cgroup/treadmill/apps/foo.test.sleep-001-dwZuH',
            content_type='application/json'
        )
        self.assert_response_equal(response, stats)
        self.impl.app.assert_called_once_with('foo.test.sleep-001-dwZuH')

    def test_treadmill_apps_all(self):
        """Test get all Treadmill app cgroup resources"""
        self.impl.apps.return_value = {}

        cases = (
            ('/cgroup/treadmill/apps/*/', False),
            ('/cgroup/treadmill/apps/*/?detail=true', True),
            ('/cgroup/treadmill/apps/*/?detail=false', False),
            ('/cgroup/treadmill/apps/*/?detail=1', True),
            ('/cgroup/treadmill/apps/*/?detail=0', False),
        )

        for url, detail in cases:
            self.impl.apps.reset_mock()
            response = self.client.get(url, content_type='application/json')
            self.assertEqual(response.status_code, http_client.OK)
            self.impl.apps.assert_called_once_with(detail=detail)


if __name__ == '__main__':
    unittest.main()
