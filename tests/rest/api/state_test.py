"""State REST api tests.
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
from treadmill.rest.api import state


class StateTest(unittest.TestCase):
    """Test the logic corresponding to the /state namespace."""

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

        state.init(api, cors, self.impl)
        self.client = self.app.test_client()

    def test_get_state_list(self):
        """Test getting a state list."""
        self.impl.list.return_value = [
            {'name': 'foo.bar#0000000001', 'host': 'baz1', 'state': 'running'},
            {'name': 'foo.bar#0000000002', 'host': 'baz2', 'state': 'finished',
             'when': '1234567890.1', 'exitcode': 0, 'oom': False},
            {'name': 'foo.bar#0000000003', 'host': 'baz3', 'state': 'finished',
             'when': '1234567890.2', 'signal': 11, 'oom': False}
        ]

        resp = self.client.get('/state/')
        resp_json = b''.join(resp.response)
        self.assertEqual(
            json.loads(resp_json.decode()),
            [
                {'name': 'foo.bar#0000000001', 'oom': None, 'signal': None,
                 'expires': None, 'when': None, 'host': 'baz1',
                 'state': 'running', 'exitcode': None, 'aborted_reason': None},
                {'name': 'foo.bar#0000000002', 'oom': False, 'signal': None,
                 'expires': None, 'when': 1234567890.1, 'host': 'baz2',
                 'state': 'finished', 'exitcode': 0, 'aborted_reason': None},
                {'name': 'foo.bar#0000000003', 'oom': False, 'signal': 11,
                 'expires': None, 'when': 1234567890.2, 'host': 'baz3',
                 'state': 'finished', 'exitcode': None, 'aborted_reason': None}
            ]
        )
        self.assertEqual(resp.status_code, http_client.OK)
        self.impl.list.assert_called_with(None, False, None)

        resp = self.client.get('/state/?match=test*')
        self.assertEqual(resp.status_code, http_client.OK)
        self.impl.list.assert_called_with('test*', False, None)

        resp = self.client.get('/state/?finished=true')
        self.assertEqual(resp.status_code, http_client.OK)
        self.impl.list.assert_called_with(None, True, None)

        resp = self.client.get('/state/?finished=false')
        self.assertEqual(resp.status_code, http_client.OK)
        self.impl.list.assert_called_with(None, False, None)

        resp = self.client.get('/state/?match=test*&finished=true')
        self.assertEqual(resp.status_code, http_client.OK)
        self.impl.list.assert_called_with('test*', True, None)

        resp = self.client.get(
            '/state/?match=test*&finished=true&partition=part1'
        )
        self.assertEqual(resp.status_code, http_client.OK)
        self.impl.list.assert_called_with('test*', True, 'part1')

    @unittest.skip('BROKEN: Flask exception handling')  # FIXME
    def test_get_state(self):
        """Test getting an instance state."""
        self.impl.get.return_value = {
            'name': 'foo.bar#0000000001', 'host': 'baz1', 'state': 'running'
        }

        resp = self.client.get('/state/foo.bar#0000000001')
        resp_json = b''.join(resp.response)
        self.assertEqual(
            json.loads(resp_json.decode()),
            {
                'name': 'foo.bar#0000000001', 'oom': None, 'signal': None,
                'expires': None, 'when': None, 'host': 'baz1',
                'state': 'running', 'exitcode': None, 'aborted_reason': None
            }
        )
        self.assertEqual(resp.status_code, http_client.OK)
        self.impl.get.assert_called_with('foo.bar#0000000001')

    @unittest.skip('BROKEN: Flask exception handling')  # FIXME
    def test_get_state_notfound(self):
        """Test getting an instance state (not found)."""
        self.impl.get.return_value = None
        resp = self.client.get('/state/foo.bar#0000000002')
        self.assertEqual(resp.status_code, http_client.NOT_FOUND)


if __name__ == '__main__':
    unittest.main()
