"""Unit test for webutils.
"""

import unittest

import flask

from treadmill import webutils


def trimall(string):
    """Removes all whitespaces and eol chars from the string."""
    return ''.join(
        string.splitlines()).strip().replace(' ', '').replace('\t', '')


class WebUtilsTest(unittest.TestCase):
    """Tests for teadmill.webutils."""

    def test_jsonp(self):
        """Tests jsonp decorator."""
        app = flask.Flask(__name__)
        app.testing = True

        @app.route('/xxx')
        @webutils.jsonp
        def handler_unused():
            """Name does not matter, flask will route the request."""
            return flask.jsonify({'apps': 1})

        resp = app.test_client().get('/xxx')
        self.assertEqual(resp.mimetype, 'application/json')
        self.assertEqual({'apps': 1}, flask.json.loads(resp.data))

        resp = app.test_client().get('/xxx?callback=foo')
        self.assertEqual(resp.mimetype, 'application/json')
        expected = 'foo({"apps":1})'
        self.assertEqual(expected, trimall(resp.get_data(as_text=True)))

    def test_cors(self):
        """Tests cors decorator."""
        app = flask.Flask(__name__)
        app.testing = True

        @app.route('/xxx')
        @webutils.cors(origin='*', content_type='application/json')
        def handler_unused():
            """Name does not matter, flask will route the request."""
            return flask.jsonify({'apps': 1})

        resp = app.test_client().get('/xxx')
        self.assertEqual(resp.mimetype, 'application/json')
        self.assertEqual({'apps': 1}, flask.json.loads(resp.data))

        self.assertIn('Access-Control-Allow-Origin', resp.headers)
        self.assertEqual('*', resp.headers['Access-Control-Allow-Origin'])


if __name__ == '__main__':
    unittest.main()
