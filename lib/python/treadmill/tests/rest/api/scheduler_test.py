"""Scheduler reports REST api tests."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import unittest

import flask
import flask_restplus as restplus
import mock

import pandas as pd

from treadmill import rest
from treadmill import webutils
from treadmill.rest import error_handlers  # pylint: disable=no-name-in-module
from treadmill.rest.api import scheduler  # pylint: disable=no-name-in-module


class ReportTest(unittest.TestCase):
    """Test the scheduler reports REST api."""

    def setUp(self):
        """Initialize the app with the corresponding logic."""
        self.app = flask.Flask(__name__)
        self.app.testing = True
        self.app.json_encoder = rest.CompliantJsonEncoder

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
            [[1, 2, 3], [float('nan'), float('inf'), float('-inf')]],
            columns=['a', 'b', 'c']
        )

        resp = self.client.get('/scheduler/servers')
        resp_json = b''.join(resp.response)
        self.assertEqual(
            json.loads(resp_json.decode()),
            {
                'columns': ['a', 'b', 'c'],
                'data': [
                    [1.0, 2.0, 3.0],
                    [None, None, None]
                ]
            }
        )

    def test_get_match(self):
        """Test fetching report with match."""
        self.impl.get.return_value = pd.DataFrame(
            [['findme', 2, 3]],
            columns=['name', 'b', 'c']
        )
        self.client.get('/scheduler/servers?match=findme')
        self.impl.get.assert_called_with(
            'servers', match='findme', partition=None
        )

    def test_get_partition(self):
        """Test fetching report with partition."""
        self.impl.get.return_value = pd.DataFrame(
            [['findme', 2, 3, 'part1']],
            columns=['name', 'b', 'c', 'd']
        )
        self.client.get('/scheduler/servers?partition=part1')
        self.impl.get.assert_called_with(
            'servers', match=None, partition='part1'
        )

    def test_get_explain(self):
        """Test GET on /scheduler/explain path."""
        self.impl.explain.get.return_value = pd.DataFrame(
            [['host.ms.com', True, True, False]],
            columns=['name', 'disk', 'cpu', 'mem']
        )
        self.client.get('/scheduler/explain/proid.app#123')
        self.impl.explain.get.assert_called_with('proid.app#123')


if __name__ == '__main__':
    unittest.main()
