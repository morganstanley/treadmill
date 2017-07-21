"""Cloud Host API tests."""

import unittest

import mock

from treadmill.api import cloud_host
import subprocess


class ApiCloudHostTest(unittest.TestCase):
    """treadmill.api.cloud_host tests."""

    def setUp(self):
        self.cloud_host = cloud_host.API()

    def tearDown(self):
        pass

    def test_create(self):
        _ipa_result_mock = b'foo\n bar\n goo\n tao\n random password: tao-pass-goo-foo' # noqa :E501
        subprocess.check_output = mock.Mock(return_value=_ipa_result_mock)

        self.assertEqual(
            self.cloud_host.create('some-host'),
            'tao-pass-goo-foo'
        )

        subprocess.check_output.assert_called_once_with([
            "ipa",
            "host-add",
            'some-host',
            "--random",
            "--force"
        ])

    def test_delete(self):
        _ipa_result_mock = b'------------------\nDeleted host "some-host"\n------------------\n' # noqa :E501
        subprocess.check_output = mock.Mock(return_value=_ipa_result_mock)

        self.cloud_host.delete('some-host')

        subprocess.check_output.assert_called_once_with([
            "ipa",
            "host-del",
            'some-host'
        ])

    def test_delete_failure(self):
        _ipa_result_mock = b'------------------\nCould not Delete host "some-host"\n------------------\n' # noqa :E501
        subprocess.check_output = mock.Mock(return_value=_ipa_result_mock)

        with self.assertRaises(AssertionError):
            self.cloud_host.delete('some-host')

        subprocess.check_output.assert_called_once_with([
            "ipa",
            "host-del",
            'some-host'
        ])


if __name__ == '__main__':
    unittest.main()
