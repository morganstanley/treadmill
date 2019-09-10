"""App REST API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import flask
import flask_restplus as restplus
import mock

from treadmill import webutils
from treadmill.rest import error_handlers
from treadmill.rest.api import app


class AppTest(unittest.TestCase):
    """Test the logic corresponding to the /instance namespace.
    """

    def setUp(self):
        """Initialize the app with the corresponding logic.
        """
        self.app = flask.Flask(__name__)
        self.app.testing = True

        api = restplus.Api(self.app)
        error_handlers.register(api)

        cors = webutils.cors(origin='*',
                             content_type='application/json',
                             credentials=False)
        self.impl = mock.Mock()

        app.init(api, cors, self.impl)
        self.client = self.app.test_client()

    def test_list(self):
        """Confirm list is simply passing through to the implementation's list
        method.
        """
        self.impl.list.return_value = []
        # resp = self.client.get(
        #     '/app/?match=%2A.%2A',
        # )
        resp = self.client.get(
            '/app/?match=foo.%2A',
        )
        self.impl.list.assert_called_with(match='foo.*')

    def test_list_match_valid(self):
        """Test all valid/invalid list match argument.
        """
        self.impl.list.return_value = []
        test_matchs = [
            '',                     # No match arg
            'foo.bar',
            '*.*',                  # no userid.
            'f.*a.b',               # userid too short
            'fo.*a.b',
            'foo2@bar2.(*)',        # invalid chars
            'foo2@bar2.[*]',        # invalid chars
            'foo2@bar2.*',
            'foo2@bar2.a_',
            'foo2@bar2.a_*',
            'foo2.bar.baz.*.lala.*-hz*',
            'foo2@var3.fo*.*of',
            'foo.*a.b',
            'foo*a.b',              # no '.' before first '*'
            'foo@bar.*',
            'foo@bar.*a.b',
            'foo@bar*a.b',          # no '.' before first '*'
            'foo@foo.*a.b',
            'foo@.*a.b',            # missing group name before '.'
            'foooooooooooooooooo.*a.b',
            'fooooooooooooooooooooooo.*a.b',    # userid too long
        ]

        results = [
            (
                pattern,
                self.client.get(
                    '/app/?match={pat}'.format(pat=pattern)
                ).status_code
            )
            for pattern in test_matchs
        ]

        self.assertEqual(
            results,
            [
                ('', 400),
                ('foo.bar', 200),
                ('*.*', 400),
                ('f.*a.b', 400),
                ('fo.*a.b', 200),
                ('foo2@bar2.(*)', 400),
                ('foo2@bar2.[*]', 400),
                ('foo2@bar2.*', 200),
                ('foo2@bar2.a_', 200),
                ('foo2@bar2.a_*', 200),
                ('foo2.bar.baz.*.lala.*-hz*', 200),
                ('foo2@var3.fo*.*of', 200),
                ('foo.*a.b', 200),
                ('foo*a.b', 400),
                ('foo@bar.*', 200),
                ('foo@bar.*a.b', 200),
                ('foo@bar*a.b', 400),
                ('foo@foo.*a.b', 200),
                ('foo@.*a.b', 400),
                ('foooooooooooooooooo.*a.b', 200),
                ('fooooooooooooooooooooooo.*a.b', 400),
            ]
        )


if __name__ == '__main__':
    unittest.main()
