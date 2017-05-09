"""
Unit test for identity_group websocket API.
"""

import unittest

import jsonschema

from treadmill.websocket.api import identity_group


class WSIdentityGroupAPITest(unittest.TestCase):
    """Tests for identity group websocket API."""

    def test_subscribe(self):
        """Test subscription registration."""
        api = identity_group.IdentityGroupAPI()
        self.assertEquals(
            [('/identity-groups/foo.bar', '*')],
            api.subscribe({'topic': '/identity-groups',
                           'identity-group': 'foo.bar'})
        )

        self.assertEquals(
            [('/identity-groups/foo.*', '*')],
            api.subscribe({'topic': '/identity-groups',
                           'identity-group': 'foo.*'})
        )

        self.assertEquals(
            [('/identity-groups/*', '*')],
            api.subscribe({'topic': '/identity-groups'})
        )

        with self.assertRaisesRegexp(
            jsonschema.exceptions.ValidationError,
            "'filter' was unexpected"
        ):
            api.subscribe({'topic': '/identity-groups',
                           'filter': 'foo!'})

        with self.assertRaisesRegexp(
            jsonschema.exceptions.ValidationError,
            "None is not of type 'string'"
        ):
            api.subscribe({'topic': '/identity-groups',
                           'identity-group': None})

    def test_on_event(self):
        """Tests payload generation."""
        api = identity_group.IdentityGroupAPI()
        self.assertEquals(
            {'topic': '/identity-groups',
             'identity-group': 'foo.bar',
             'identity': 3,
             'host': 'xxx.xx.com',
             'app': 'foo.bar#123',
             'sow': True},
            api.on_event(
                '/identity-groups/foo.bar/3',
                None,
                '{"host": "xxx.xx.com", "app": "foo.bar#123"}'
            )
        )
        self.assertEquals(
            {'topic': '/identity-groups',
             'identity-group': 'foo.bar',
             'identity': 3,
             'host': None,
             'app': None,
             'sow': False},
            api.on_event(
                '/identity-groups/foo.bar/3',
                'd',
                None
            )
        )


if __name__ == '__main__':
    unittest.main()
