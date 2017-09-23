"""Scheduler reports REST api tests."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import flask
import flask_restplus as restplus
import mock

import pandas as pd

from treadmill import webutils
from treadmill.rest import error_handlers
from treadmill.rest.api import scheduler


class ReportTest(unittest.TestCase):
    """Test the scheduler reports REST api."""

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

        scheduler.init(api, cors, self.impl)
        self.client = self.app.test_client()

    def test_get(self):
        """Test fetching a report."""
        self.impl.get.return_value = pd.DataFrame(
            [[1, 2, 3], [4, 5, 6]],
            columns=["a", "b", "c"]
        )

        resp = self.client.get('/scheduler/servers')
        self.assertEqual(
            ''.join(resp.response),
            '{"data": [[1, 2, 3], [4, 5, 6]], "columns": ["a", "b", "c"]}'
        )

    def test_get_match(self):
        """Test fetching report with match."""
        self.impl.get.return_value = pd.DataFrame(
            [["findme", 2, 3]],
            columns=["name", "b", "c"]
        )
        self.client.get('/scheduler/servers?match=findme')
        self.impl.get.assert_called_with('servers', match='findme')


if __name__ == '__main__':
    unittest.main()
