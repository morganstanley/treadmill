"""Instance REST api tests.
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

from treadmill import exc
from treadmill import webutils
from treadmill.rest import error_handlers
from treadmill.rest.api import instance

from treadmill.tests.rest.api import user_set


class InstanceTest(unittest.TestCase):
    """Test the logic corresponding to the /instance namespace."""

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

        instance.init(api, cors, self.impl)
        self.client = self.app.test_client()

    @unittest.skip('BROKEN: Flask exception handling')  # FIXME
    def test_post_instance(self):
        """Test creating an instance."""
        self.impl.create.return_value = ['proid.app#0000000001']

        rsrc = {
            'services': [{
                'command': '/bin/sleep 60',
                'name': 'sleep',
                'restart': {'interval': 60, 'limit': 0}
            }],
            'cpu': '10%',
            'memory': '100M',
            'disk': '100M'
        }

        resp = self.client.post(
            '/instance/proid.app',
            data=json.dumps(rsrc),
            content_type='application/json'
        )
        resp_json = b''.join(resp.response)
        self.assertEqual(
            json.loads(resp_json.decode()),
            {'instances': ['proid.app#0000000001']}
        )
        self.assertEqual(resp.status_code, http_client.OK)
        self.impl.create.assert_called_once_with(
            'proid.app', rsrc, 1, None, False, None
        )

        self.impl.reset_mock()
        with user_set(self.app, 'foo@BAR.BAZ'):
            resp = self.client.post(
                '/instance/proid.app?count=2',
                data=json.dumps(rsrc),
                content_type='application/json'
            )
            self.assertEqual(resp.status_code, http_client.OK)
            self.impl.create.assert_called_once_with(
                'proid.app', rsrc, 2, 'foo@BAR.BAZ', False, None
            )

        self.impl.reset_mock()
        resp = self.client.post(
            '/instance/proid.app?count=1&debug=true',
            data=json.dumps(rsrc),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, http_client.OK)
        self.impl.create.assert_called_once_with(
            'proid.app', rsrc, 1, None, True, None
        )

        self.impl.reset_mock()
        resp = self.client.post(
            '/instance/proid.app?count=1&debug_services=test',
            data=json.dumps(rsrc),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, http_client.OK)
        self.impl.create.assert_called_once_with(
            'proid.app', rsrc, 1, None, False, ['test']
        )

        self.impl.create.side_effect = exc.InvalidInputError('foo', 'bar')
        resp = self.client.post(
            '/instance/user@group.app',
            data=json.dumps(rsrc),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, http_client.BAD_REQUEST)

    def test_delete_instance(self):
        """Test deleting an instance."""
        self.impl.delete.return_value = None

        resp = self.client.delete('/instance/proid.app#0000000001')
        self.assertEqual(resp.status_code, http_client.OK)
        self.impl.delete.assert_called_once_with('proid.app#0000000001', None)

        self.impl.reset_mock()
        with user_set(self.app, 'foo@BAR.BAZ'):
            resp = self.client.delete('/instance/proid.app#0000000001')
            self.assertEqual(resp.status_code, http_client.OK)
            self.impl.delete.assert_called_once_with(
                'proid.app#0000000001', 'foo@BAR.BAZ'
            )

    def test_bulk_delete_instance(self):
        """Test bulk deleting list of instances."""
        self.impl.bulk_delete.return_value = None

        resp = self.client.post(
            '/instance/_bulk/delete',
            data=json.dumps({
                'instances': ['proid.app#0000000001', 'proid.app#0000000002']
            }),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, http_client.OK)
        self.assertEqual(self.impl.bulk_delete.call_args_list, [
            mock.call(
                'proid',
                ['proid.app#0000000001', 'proid.app#0000000002'],
                None),
        ])

        self.impl.reset_mock()
        with user_set(self.app, 'foo@BAR.BAZ'):
            resp = self.client.post(
                '/instance/_bulk/delete',
                data=json.dumps({
                    'instances': [
                        'proid.app#0000000001', 'proid.app#0000000002'
                    ]
                }),
                content_type='application/json'
            )
            self.assertEqual(resp.status_code, http_client.OK)
            self.assertEqual(self.impl.bulk_delete.call_args_list, [
                mock.call(
                    'proid',
                    ['proid.app#0000000001', 'proid.app#0000000002'],
                    'foo@BAR.BAZ'
                ),
            ])

    def test_bulk_update_instance(self):
        """Test bulk updateing list of instances."""
        self.impl.bulk_update.return_value = None

        resp = self.client.post(
            '/instance/_bulk/update',
            data=json.dumps({
                'instances': [
                    {'_id': 'proid.app#0000000001',
                     'priority': 10},
                    {'_id': 'proid.app#0000000002',
                     'priority': 10}
                ]
            }),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, http_client.OK)
        self.assertEqual(self.impl.bulk_update.call_args_list, [
            mock.call('proid', [
                {'_id': 'proid.app#0000000001',
                 'priority': 10},
                {'_id': 'proid.app#0000000002',
                 'priority': 10}
            ]),
        ])


if __name__ == '__main__':
    unittest.main()
