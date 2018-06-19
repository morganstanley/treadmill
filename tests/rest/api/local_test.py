"""Local node REST api tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import sys
import unittest

import flask
import flask_restplus as restplus
import mock

import six
from six.moves import http_client

from treadmill import webutils
from treadmill.exc import LocalFileNotFoundError
from treadmill.rest import error_handlers
from treadmill.rest.api import local

LOG_CONTENT = list(six.moves.range(1, 10))


# Don't complain about unused parameters
# pylint: disable=W0613
def return_params(*args, **kwargs):
    """Return the parameters."""
    return json.dumps(kwargs)


# Don't complain about unused parameters
# pylint: disable=W0613
def get_log_success(*args, **kwargs):
    """Generator w/o any exception."""
    for line in LOG_CONTENT:
        yield line


class LocalTest(unittest.TestCase):
    """Test the logic corresponding to the /local-app and /archive namespace"""

    def setUp(self):
        """Initialize the app with the corresponding logic."""
        self.app = flask.Flask(__name__)
        self.app.testing = True
        self.impl = mock.Mock()

        api = restplus.Api(self.app)
        cors = webutils.cors(origin='*',
                             content_type='application/json',
                             credentials=False)

        error_handlers.register(api)

        local.init(api, cors, self.impl)
        self.client = self.app.test_client()

    def test_app_log_fragment(self):
        """Checking that the params for getting log fragments are passed."""
        self.impl.log.get.side_effect = return_params

        resp = self.client.get(
            '/local-app/proid.app/uniq/service/service_name'
        )

        resp_json = b''.join(resp.response)
        self.assertEqual(
            json.loads(resp_json.decode()),
            {'start': 0, 'limit': -1, 'order': 'asc'}
        )
        self.assertEqual(resp.status_code, http_client.OK)

        resp = self.client.get(
            '/local-app/proid.app/uniq/service/service_name?start=0&limit=5')

        resp_json = b''.join(resp.response)
        self.assertEqual(
            json.loads(resp_json.decode()),
            {'start': 0, 'limit': 5, 'order': 'asc'}
        )
        self.assertEqual(resp.status_code, http_client.OK)

        resp = self.client.get(
            '/local-app/proid.app/uniq/sys/component'
            '?start=3&limit=9&order=desc'
        )
        resp_json = b''.join(resp.response)
        self.assertEqual(
            json.loads(resp_json.decode()),
            {'start': 3, 'limit': 9, 'order': 'desc'}
        )
        self.assertEqual(resp.status_code, http_client.OK)

    @mock.patch('flask.send_file', mock.Mock(return_value=flask.Response()))
    def test_app_log_success(self):
        """Dummy tests for returning application logs."""
        self.impl.log.get.side_effect = get_log_success

        resp = self.client.get(
            '/local-app/proid.app/uniq/service/service_name'
        )
        self.assertEqual(list(resp.response), LOG_CONTENT)
        self.assertEqual(resp.status_code, http_client.OK)

        resp = self.client.get('/local-app/proid.app/uniq/sys/component')
        self.assertEqual(list(resp.response), LOG_CONTENT)
        self.assertEqual(resp.status_code, http_client.OK)

        # check that get_all() is called if 'all' in query string is not 0
        self.client.get(
            '/local-app/proid.app/uniq/service/service_name?all=0'
        )
        self.assertFalse(self.impl.log.get_all.called)
        self.client.get(
            '/local-app/proid.app/uniq/service/service_name?all=1'
        )
        self.assertTrue(self.impl.log.get_all.called)

        self.impl.log.reset_mock()
        self.client.get(
            '/local-app/proid.app/uniq/sys/component?all=0'
        )
        self.assertFalse(self.impl.log.get_all.called)
        self.client.get(
            '/local-app/proid.app/uniq/sys/component?all=1'
        )
        self.assertTrue(self.impl.log.get_all.called)

    @unittest.skip('BROKEN: Flask exception handling')  # FIXME
    def test_app_log_failure(self):
        """Dummy tests for the case when logs cannot be found."""
        self.impl.log.get.side_effect = LocalFileNotFoundError('foo')

        resp = self.client.get(
            '/local-app/proid.app/uniq/service/service_name'
        )
        self.assertEqual(resp.status_code, http_client.NOT_FOUND)

        resp = self.client.get('/local-app/proid.app/uniq/sys/component')
        self.assertEqual(resp.status_code, http_client.NOT_FOUND)

    def test_arch_get(self):
        """Dummy tests for returning application archives.
        """
        # File need to exist for flask to send it.
        self.impl.archive.get.return_value = sys.executable
        resp = self.client.get('/archive/<app>/<uniq>/app')
        self.assertEqual(resp.status_code, http_client.OK)

    @unittest.skip('BROKEN: Flask exception handling')  # FIXME
    def test_arch_get_err(self):
        """Dummy tests for returning application archives (not found)
        """
        self.impl.archive.get.side_effect = LocalFileNotFoundError('foo')

        resp = self.client.get('/archive/<app>/<uniq>/app')
        self.assertEqual(resp.status_code, http_client.NOT_FOUND)
        resp = self.client.get('/archive/<app>/<uniq>/sys')
        self.assertEqual(resp.status_code, http_client.NOT_FOUND)


if __name__ == '__main__':
    unittest.main()
