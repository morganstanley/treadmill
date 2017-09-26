"""Unit test for treadmill.sproc.api_discover.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import json

import mock

from treadmill import rest
from treadmill.sproc import api_discover
from treadmill import admin

from six.moves import http_client

from ldap3.core import exceptions as ldap_exceptions


class ApiDiscoverGetTest(unittest.TestCase):
    """Test treadmill.sproc.api_discover GET calls"""

    GLOBAL = mock.MagicMock()
    GLOBAL.dns_domain = mock.Mock(return_value='dns_domain')
    LDAP = mock.MagicMock()
    LDAP.conn = mock.Mock(return_value={})
    GLOBAL.ldap = mock.Mock(return_value=LDAP)

    LBENDPOINTS = {'data': [
        'vips=treadmill-ln-foobar.foo.com,treadmill-ny-foobar.foo.com',
        'port=9876'
    ]}
    ADMIN_AG_LB = mock.MagicMock(admin.AppGroup)
    ADMIN_AG_LB.get = mock.Mock(return_value=LBENDPOINTS)

    ADMIN_AG_NO_LB = mock.MagicMock(admin.AppGroup)
    ADMIN_AG_NO_LB.get = mock.Mock(
        side_effect=ldap_exceptions.LDAPNoSuchObjectResult
    )

    @classmethod
    def setUpClass(cls):
        """Set up once"""
        cls.app = rest.FLASK_APP.test_client()
        cls.app.testing = True
        api_discover.setup_server({'type1': 'http',
                                   'type2': 'p2'}, 'ny', '.*')
        super(cls)

    @mock.patch('treadmill.context.GLOBAL', return_value=mock.MagicMock())
    @mock.patch('treadmill.admin.AppGroup', return_value=ADMIN_AG_LB)
    def test_redir_no_path_with_lb(self, *_args):
        """Test redirect with no path and existing LB"""
        resp = self.app.get('/redir/lb/type1/cell1')
        self.assertEqual(resp.status_code, http_client.TEMPORARY_REDIRECT)
        self.assertIn(resp.headers.get('Location'),
                      'http://treadmill-ny-foobar.foo.com:9876')

    @mock.patch('treadmill.context.GLOBAL', return_value=mock.MagicMock())
    @mock.patch('treadmill.admin.AppGroup', return_value=ADMIN_AG_NO_LB)
    def test_redir_no_path_no_lb(self, *_args):
        """Test redirect with no path and no LB"""
        resp = self.app.get('/redir/lb/type1/cell1')
        self.assertEqual(resp.status_code, http_client.NOT_FOUND)

    @mock.patch('treadmill.context.GLOBAL', return_value=mock.MagicMock())
    @mock.patch('treadmill.admin.AppGroup', return_value=ADMIN_AG_LB)
    def test_redir_path_with_lb(self, *_args):
        """Test redirect with given path and existing LB"""
        resp = self.app.get('/redir/lb/type1/cell1/my/path')
        self.assertEqual(resp.status_code, http_client.TEMPORARY_REDIRECT)
        self.assertIn(resp.headers.get('Location'),
                      'http://treadmill-ny-foobar.foo.com:9876/my/path')

    @mock.patch('treadmill.context.GLOBAL', return_value=GLOBAL)
    @mock.patch('treadmill.admin.AppGroup', return_value=ADMIN_AG_LB)
    def test_redir_path_no_lb(self, *_args):
        """Test redirect with given path and no LB"""
        resp = self.app.get('/redir/lb/type1/cell1/my/path')
        self.assertEqual(resp.status_code, http_client.TEMPORARY_REDIRECT)
        self.assertIn(resp.headers.get('Location'),
                      'http://treadmill-ny-foobar.foo.com:9876/my/path')

    @mock.patch('treadmill.context.GLOBAL', return_value=mock.MagicMock())
    @mock.patch('treadmill.admin.AppGroup', return_value=ADMIN_AG_LB)
    def test_json_no_path_lb(self, *_args):
        """Test json response with no path and with lb"""
        resp = self.app.get('/json/lb/type2/cell1')
        self.assertEqual(resp.status_code, http_client.OK)
        payload = json.loads(resp.data)
        self.assertEqual(payload['target'],
                         'p2://treadmill-ny-foobar.foo.com:9876')

    @mock.patch('treadmill.context.GLOBAL', return_value=mock.MagicMock())
    @mock.patch('treadmill.admin.AppGroup', return_value=ADMIN_AG_NO_LB)
    @mock.patch('treadmill.dnsutils.srv',
                return_value=mock.Mock(return_value=[('unused')]))
    @mock.patch('random.choice', return_value=('host', 1234, 1, 1))
    def test_json_path_no_lb(self, *_args):
        """Test json response with path and no lb"""
        resp = self.app.get('/json/srv/type2/cell1/foo/bar')
        self.assertEqual(resp.status_code, http_client.OK)
        payload = json.loads(resp.data)
        self.assertEqual(payload['target'], 'p2://host:1234/foo/bar')

    @mock.patch('treadmill.context.GLOBAL', return_value=mock.MagicMock())
    @mock.patch('treadmill.admin.AppGroup', return_value=ADMIN_AG_NO_LB)
    @mock.patch('treadmill.dnsutils.srv',
                return_value=mock.Mock(return_value=[('unused')]))
    @mock.patch('random.choice', return_value=('host', 1234, 1, 1))
    def test_redir_not_allowed(self, *_args):
        """Test redirection not allowed error when protocol not http"""
        resp = self.app.get('/redir/srv/type2/cell1/foo/bar')
        self.assertEqual(resp.status_code, http_client.BAD_REQUEST)
        payload = json.loads(resp.data)
        self.assertEqual('Redirection not allowed for p2 protocol',
                         payload['message'])

    @mock.patch('treadmill.context.GLOBAL', return_value=mock.MagicMock())
    @mock.patch('treadmill.admin.AppGroup', return_value=ADMIN_AG_NO_LB)
    @mock.patch('treadmill.dnsutils.srv', return_value=[])
    def test_no_srv_records(self, *_args):
        """Test no srv records error when no LB and no SRV records"""
        resp = self.app.get('/redir/srv/type1/cell1/foo/bar')
        self.assertEqual(resp.status_code, http_client.NOT_FOUND)
        payload = json.loads(resp.data)
        self.assertEqual('No SRV records found for '
                         '_http._tcp.type1api.cell1.cell',
                         payload['message'])

    @mock.patch('treadmill.context.GLOBAL', return_value=mock.MagicMock())
    @mock.patch('treadmill.admin.AppGroup', return_value=ADMIN_AG_LB)
    def test_url_part_encoding(self, *_args):
        """Test whether api_discover encodes URI components"""
        resp = self.app.get('/json/lb/type1/cell1/foo/bar%2312340230492304')
        self.assertEqual(resp.status_code, http_client.OK)
        payload = json.loads(resp.data)
        self.assertEqual('http://treadmill-ny-foobar.foo.com:9876'
                         '/foo/bar%2312340230492304',
                         payload['target'])


if __name__ == '__main__':
    unittest.main()
