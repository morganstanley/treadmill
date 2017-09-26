"""Local node REST api tests.
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


# W0613: Don't complain about unused parameters
# W0101: Don't complain about unreachable code
# pylint: disable=W0613,W0101
def get_log_failure(*args, **kwargs):
    """Generator w/ exception."""
    raise LocalFileNotFoundError('Something went wrong')
    for line in LOG_CONTENT:
        return line
        # yield line


def err(*args, **kwargs):
    """Raise LocalFileNotFoundError."""
    raise LocalFileNotFoundError('File not found')


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

        self.assertEqual(''.join(resp.response),
                         '{"start": 0, "limit": -1, "order": "asc"}')
        self.assertEqual(resp.status_code, http_client.OK)

        resp = self.client.get(
            '/local-app/proid.app/uniq/service/service_name?start=0&limit=5')

        self.assertEqual(''.join(resp.response),
                         '{"start": 0, "limit": 5, "order": "asc"}')
        self.assertEqual(resp.status_code, http_client.OK)

        resp = self.client.get(
            '/local-app/proid.app/uniq/sys/component'
            '?start=3&limit=9&order=desc'
        )
        self.assertEqual(''.join(resp.response),
                         '{"start": 3, "limit": 9, "order": "desc"}')
        self.assertEqual(resp.status_code, http_client.OK)

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

    @unittest.skip('BROKEN: Flask exception handling')
    def test_app_log_failure(self):
        """Dummy tests for the case when logs cannot be found."""
        self.impl.log.get.side_effect = get_log_failure

        resp = self.client.get(
            '/local-app/proid.app/uniq/service/service_name'
        )
        self.assertEqual(resp.status_code, http_client.NOT_FOUND)

        resp = self.client.get('/local-app/proid.app/uniq/sys/component')
        self.assertEqual(resp.status_code, http_client.NOT_FOUND)

    @unittest.skip('BROKEN: Flask exception handling')
    def test_arch_get(self):
        """Dummy tests for returning application archives."""
        self.impl.archive.get.return_value = __file__

        resp = self.client.get('/archive/<app>/<uniq>/app')
        self.assertEqual(resp.status_code, http_client.OK)

        self.impl.archive.get.side_effect = err

        resp = self.client.get('/archive/<app>/<uniq>/app')
        self.assertEqual(resp.status_code, http_client.NOT_FOUND)
        resp = self.client.get('/archive/<app>/<uniq>/sys')
        self.assertEqual(resp.status_code, http_client.NOT_FOUND)


if __name__ == '__main__':
    unittest.main()
