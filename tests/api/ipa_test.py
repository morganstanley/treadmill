'''IPA API tests.'''

import unittest

import mock

from treadmill.api import ipa
import subprocess


class ApiIPATest(unittest.TestCase):
    '''treadmill.api.ipa tests.'''

    def setUp(self):
        self.ipa = ipa.API()

    def tearDown(self):
        pass

    def test_add_host(self):
        _ipa_result_mock = b'foo\n bar\n goo\n tao\n random password: tao-pass-goo-foo' # noqa :E501
        subprocess.check_output = mock.Mock(return_value=_ipa_result_mock)

        self.assertEqual(
            self.ipa.add_host(hostname='some-host'),
            'tao-pass-goo-foo'
        )

        subprocess.check_output.assert_called_once_with([
            'ipa',
            'host-add',
            'some-host',
            '--random',
            '--force'
        ])

    def test_delete_host(self):
        _ipa_result_mock = b'------------------\nDeleted host "some-host"\n------------------\n' # noqa :E501
        subprocess.check_output = mock.Mock(return_value=_ipa_result_mock)

        self.ipa.delete_host(hostname='some-host')

        subprocess.check_output.assert_called_once_with([
            'ipa',
            'host-del',
            'some-host'
        ])

    def test_delete_host_failure(self):
        _ipa_result_mock = b'------------------\nCould not Delete host "some-host"\n------------------\n' # noqa :E501
        subprocess.check_output = mock.Mock(return_value=_ipa_result_mock)

        with self.assertRaises(AssertionError):
            self.ipa.delete_host(hostname='some-host')

        subprocess.check_output.assert_called_once_with([
            'ipa',
            'host-del',
            'some-host'
        ])

    def test_service_add(self):
        _ipa_result_mock = b'------------------\nmembers added 1\n------------------\n' # noqa :E501
        subprocess.check_output = mock.Mock(return_value=_ipa_result_mock)

        self.ipa.service_add(
            protocol='prot',
            service='some-service',
            args={
                'domain': 'some-domain',
                'hostname': 'some-host',
            }
        )

        self.assertEqual(
            subprocess.check_output.mock_calls,
            [
                mock.call([
                    'ipa',
                    'service-add',
                    '--force',
                    'prot/some-service'
                ]),
                mock.call([
                    'ipa',
                    'service-allow-retrieve-keytab',
                    'prot/some-service@SOME-DOMAIN',
                    '--hosts=some-host'
                ])
            ]
        )


if __name__ == '__main__':
    unittest.main()
