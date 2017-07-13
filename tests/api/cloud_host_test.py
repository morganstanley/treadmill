"""Cloud Host API tests."""

import unittest

import mock

from treadmill.api import cloud_host
import subprocess


class ApiCellTest(unittest.TestCase):
    """treadmill.api.cloud_host tests."""

    def setUp(self):
        self.cloud_host = cloud_host.API()

    def tearDown(self):
        pass

    def test_create(self):
        _ipa_result_mock = b'foo\n bar\n goo\n tao\n random password: tao-pass-goo-foo' # noqa :E501
        subprocess.check_output = mock.create_autospec(
            subprocess.check_output,
            return_value=_ipa_result_mock
        )

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


if __name__ == '__main__':
    unittest.main()
