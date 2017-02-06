"""Unit test for treadmill.restclient
"""

import unittest
import http.client

import mock
import simplejson.scanner as sjs
import requests

from treadmill import restclient


class RESTClientTest(unittest.TestCase):
    """Mock test for RESTClient"""

    def setUp(self):
        """Setup common test variables"""
        pass

    @mock.patch('requests.get',
                return_value=mock.MagicMock(requests.Response))
    def test_get_ok(self, resp_mock):
        """Test treadmill.restclient.get OK (200)"""
        resp_mock.return_value.status_code = http.client.OK
        resp_mock.return_value.text = 'foo'

        resp = restclient.get('http://foo.com', '/')

        self.assertIsNotNone(resp)
        self.assertEqual(resp.text, 'foo')

    @mock.patch('requests.get',
                return_value=mock.MagicMock(requests.Response))
    def test_get_404(self, resp_mock):
        """Test treadmill.restclient.get NOT_FOUND (404)"""
        resp_mock.return_value.status_code = http.client.NOT_FOUND

        with self.assertRaises(restclient.NotFoundError):
            restclient.get('http://foo.com', '/')

    @mock.patch('requests.get',
                return_value=mock.MagicMock(requests.Response))
    def test_get_302(self, resp_mock):
        """Test treadmill.restclient.get FOUND (302)"""
        resp_mock.return_value.status_code = http.client.FOUND

        with self.assertRaises(restclient.AlreadyExistsError):
            restclient.get('http://foo.com', '/')

    @mock.patch('requests.get',
                return_value=mock.MagicMock(requests.Response))
    def test_get_424(self, resp_mock):
        """Test treadmill.restclient.get FAILED_DEPENDENCY (424)"""
        resp_mock.return_value.status_code = http.client.FAILED_DEPENDENCY
        resp_mock.return_value.json.return_value = {}

        with self.assertRaises(restclient.ValidationError):
            restclient.get('http://foo.com', '/')

    @mock.patch('requests.get',
                return_value=mock.MagicMock(requests.Response))
    def test_get_401(self, resp_mock):
        """Test treadmill.restclient.get UNAUTHORIZED (401)"""
        resp_mock.return_value.status_code = http.client.UNAUTHORIZED
        resp_mock.return_value.json.return_value = {}

        with self.assertRaises(restclient.NotAuthorizedError):
            restclient.get('http://foo.com', '/')

    @mock.patch('requests.get',
                return_value=mock.MagicMock(requests.Response))
    def test_get_bad_json(self, resp_mock):
        """Test treadmill.restclient.get bad JSON"""
        resp_mock.return_value.status_code = http.client.INTERNAL_SERVER_ERROR
        resp_mock.return_value.text = '{"bad json"'
        resp_mock.return_value.json.side_effect = sjs.JSONDecodeError(
            'Foo', '{"bad json"', 1
        )

        self.assertRaises(
            restclient.MaxRequestRetriesError,
            restclient.get, 'http://foo.com', '/', retries=1)

    @mock.patch('time.sleep', mock.Mock())
    @mock.patch('treadmill.restclient._handle_error', mock.Mock())
    @mock.patch('treadmill.restclient._should_retry',
                mock.Mock(return_value=True))
    @mock.patch('requests.get', mock.Mock())
    def test_retry(self):
        """Tests retry logic."""

        self.assertRaises(
            restclient.MaxRequestRetriesError,
            restclient.get,
            ['http://foo.com', 'http://bla.com'], '/xxx', retries=2)

        # Requests are done in order, by because other methods are being
        # callled, to make test simpler, any_order is set to True so that
        # test will pass.
        requests.get.assert_has_calls([
            mock.call('http://foo.com/xxx', json=None, proxies=None,
                      headers=None, auth=mock.ANY, timeout=(.5, 10)),
            mock.call('http://bla.com/xxx', json=None, proxies=None,
                      headers=None, auth=mock.ANY, timeout=(.5, 10)),
            mock.call('http://foo.com/xxx', json=None, proxies=None,
                      headers=None, auth=mock.ANY, timeout=(1.5, 10)),
            mock.call('http://bla.com/xxx', json=None, proxies=None,
                      headers=None, auth=mock.ANY, timeout=(1.5, 10)),
        ], any_order=True)


if __name__ == '__main__':
    unittest.main()
