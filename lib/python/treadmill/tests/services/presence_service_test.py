"""Unit test for presence_service - Treadmill Presence configuration service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import os
import shutil
import tempfile
import unittest

import kazoo
import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import services
from treadmill.services import presence_service


class PresenceServiceTest(unittest.TestCase):
    """Unit tests for the network service implementation.
    """
    # Test accesses protected members of presence service.
    #
    # pylint:disable=W0212

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_synchronize(self):
        """Test service synchronize.
        """

    @mock.patch('treadmill.zkutils.get', mock.Mock())
    @mock.patch('treadmill.zkutils.create', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.context.ZkContext.conn', mock.MagicMock())
    def test_on_create_request(self):
        """Test processing of a network create request.
        """
        svc = presence_service.PresenceResourceService()
        request = {
            'endpoints': [{'name': 'xxx',
                           'port': 8000,
                           'real_port': 32000}]
        }
        request_id = 'foo.bar-12345-Uniq1'
        svc.on_create_request(request_id, request)
        self.assertEqual(
            svc.presence['foo.bar#12345'],
            {
                '/running/foo.bar#12345': 'foo.bar-12345-Uniq1',
                '/endpoints/foo/bar#12345:tcp:xxx': 'foo.bar-12345-Uniq1'
            }
        )

    @mock.patch('treadmill.zkutils.get', mock.Mock())
    @mock.patch('treadmill.zkutils.create', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.context.ZkContext.conn', mock.MagicMock())
    def test_on_create_with_ident(self):
        """Test processing of a network create request.
        """
        svc = presence_service.PresenceResourceService()
        request = {
            'identity': 0,
            'identity_group': 'bla',
            'endpoints': [{'name': 'xxx',
                           'port': 8000,
                           'real_port': 32000}]
        }
        request_id = 'foo.bar-12345-Uniq1'
        svc.on_create_request(request_id, request)
        self.assertEqual(
            svc.presence['foo.bar#12345'],
            {
                '/running/foo.bar#12345': 'foo.bar-12345-Uniq1',
                '/identity-groups/bla/0': 'foo.bar-12345-Uniq1',
                '/endpoints/foo/bar#12345:tcp:xxx': 'foo.bar-12345-Uniq1'
            }
        )

    @mock.patch('treadmill.zkutils.get', mock.Mock())
    @mock.patch('treadmill.zkutils.create', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.get_with_metadata', mock.Mock())
    @mock.patch('treadmill.context.ZkContext.conn', mock.MagicMock())
    def test_on_delete_request(self):
        """Test processing of a delete request.
        """
        svc = presence_service.PresenceResourceService()
        svc.zkclient.client_id = (12345, '')
        treadmill.zkutils.get_with_metadata.return_value = (
            'h.hh.com', mock.Mock(owner_session_id=12345)
        )
        request = {
            'endpoints': [{'name': 'xxx',
                           'port': 8000,
                           'real_port': 32000}]
        }
        svc.on_create_request('foo.bar-12345-Uniq2', request)

        svc.on_delete_request('foo.bar-12345-Uniq1')
        self.assertIn('foo.bar#12345', svc.presence)
        treadmill.zkutils.ensure_deleted.assert_not_called()

        svc.on_delete_request('foo.bar-12345-Uniq2')
        self.assertNotIn('foo.bar#12345', svc.presence)
        treadmill.zkutils.ensure_deleted.assert_has_calls([
            mock.call(mock.ANY, '/running/foo.bar#12345'),
            mock.call(mock.ANY, '/endpoints/foo/bar#12345:tcp:xxx')
        ], any_order=True)

    @mock.patch('kazoo.client.KazooClient.DataWatch', mock.Mock())
    @mock.patch('kazoo.client.KazooClient', mock.MagicMock())
    @mock.patch('treadmill.context.ZkContext.conn', mock.MagicMock())
    @mock.patch('treadmill.zkutils.create', mock.Mock())
    @mock.patch('treadmill.zkutils.get_with_metadata', mock.Mock())
    def test_safe_create(self):
        """Test safe create."""
        svc = presence_service.PresenceResourceService()

        # Node does not exist.
        self.assertTrue(svc._safe_create(12345,
                                         '/running/foo.bar#1234',
                                         'h.hh.com'))
        treadmill.zkutils.create.assert_called_with(
            mock.ANY,
            '/running/foo.bar#1234', 'h.hh.com', acl=[mock.ANY], ephemeral=True
        )

        # Node exists, session match.
        svc.zkclient.client_id = (12345, '')
        treadmill.zkutils.get_with_metadata.return_value = (
            'h.hh.com',
            collections.namedtuple('metadata', 'owner_session_id')(12345)
        )
        treadmill.zkutils.create.side_effect = kazoo.client.NodeExistsError
        self.assertTrue(svc._safe_create(12345,
                                         '/running/foo.bar#1234',
                                         'h.hh.com'))

        # Node exists, session does not match
        svc.zkclient.client_id = (98765, '')
        treadmill.zkutils.get_with_metadata.return_value = (
            'h.hh.com',
            collections.namedtuple('metadata', 'owner_session_id')(12345)
        )
        treadmill.zkutils.create.side_effect = kazoo.client.NodeExistsError
        self.assertFalse(svc._safe_create(12345,
                                          '/running/foo.bar#1234',
                                          'h.hh.com'))

    @mock.patch('kazoo.client.KazooClient.DataWatch', mock.Mock())
    @mock.patch('kazoo.client.KazooClient', mock.MagicMock())
    @mock.patch('treadmill.context.ZkContext.conn', mock.MagicMock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.get_with_metadata', mock.Mock())
    def test_safe_delete(self):
        """Tests safe node deletion."""
        svc = presence_service.PresenceResourceService()

        # Node exists, session match.
        svc.zkclient.client_id = (12345, '')
        treadmill.zkutils.get_with_metadata.return_value = (
            'h.hh.com',
            collections.namedtuple('metadata', 'owner_session_id')(12345)
        )

        svc._safe_delete('/running/foo.bar#1234')
        treadmill.zkutils.ensure_deleted.assert_called_with(
            mock.ANY,
            '/running/foo.bar#1234'
        )

        treadmill.zkutils.ensure_deleted.reset_mock()
        svc.zkclient.client_id = (99999, '')
        svc._safe_delete('/running/foo.bar#1234')
        self.assertFalse(treadmill.zkutils.ensure_deleted.called)

    def test_load(self):
        """Test loading service using alias."""
        # pylint: disable=W0212
        self.assertEqual(
            presence_service.PresenceResourceService,
            services.ResourceService(self.root, 'presence')._load_impl()
        )


if __name__ == '__main__':
    unittest.main()
