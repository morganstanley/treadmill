"""Unit test for treadmill.dockerutils
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import json
import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill import dockerutils


class DockerUtilsTest(unittest.TestCase):
    """Test treadmill common docker utils
    """

    @mock.patch('resource.getrlimit')
    def test_get_ulimits(self, mock_getrlimit):
        """test ulimit init method
        """
        mock_getrlimit.return_value = (1, 2)

        # pylint: disable=protected-access
        self.assertEqual(
            sorted(dockerutils.get_ulimits(), key=lambda x: x['Name']),
            [
                {'Name': 'core', 'Soft': 1, 'Hard': 2},
                {'Name': 'data', 'Soft': 1, 'Hard': 2},
                {'Name': 'fsize', 'Soft': 1, 'Hard': 2},
                {'Name': 'nofile', 'Soft': 1, 'Hard': 2},
                {'Name': 'nproc', 'Soft': 1, 'Hard': 2},
                {'Name': 'rss', 'Soft': 1, 'Hard': 2},
                {'Name': 'stack', 'Soft': 1, 'Hard': 2},
            ]
        )
        mock_getrlimit.assert_has_calls([
            mock.call(4),   # RLIMIT_CORE
            mock.call(2),   # RLIMIT_DATA
            mock.call(1),   # RLIMIT_FSIZE
            mock.call(7),   # RLIMIT_NOFILE
            mock.call(6),   # RLIMIT_NPROC
            mock.call(5),   # RLIMIT_RSS
            mock.call(3),   # RLIMIT_STACK
        ])

    def test_get_conf_legacy2(self):
        """test get registries from data (legacy compat #2)
        """
        node_data = {
            'docker_registries': {
                'qa': ['hub-qa'],
                'prod': ['hub'],
                'dev': ['hub-dev', 'hub-dev2']
            }
        }

        self.assertEqual(
            dockerutils.get_conf('dev', node_data),
            {
                'daemon_conf': {},
                'registries': [
                    {
                        'host': 'hub-dev',
                        'insecure': True,
                    },
                    {
                        'host': 'hub-dev2',
                        'insecure': True,
                    },
                ]
            }
        )
        self.assertEqual(
            dockerutils.get_conf('uat', node_data),
            {
                'daemon_conf': {},
                'registries': []
            }
        )

    def test_get_conf_legacy1(self):
        """test get registries from data (legacy compat #1)
        """
        self.assertEqual(
            dockerutils.get_conf(
                'foo',
                {'docker_registries': ['hub-dev', 'hub-dev2']}
            ),
            {
                'daemon_conf': {},
                'registries': [
                    {
                        'host': 'hub-dev',
                        'insecure': True,
                    },
                    {
                        'host': 'hub-dev2',
                        'insecure': True,
                    },
                ]
            }
        )

        self.assertEqual(
            dockerutils.get_conf(
                'foo',
                {'docker_registries': []}
            ),
            {
                'daemon_conf': {},
                'registries': []
            }
        )

    def test_get_conf(self):
        """test get registries from data
        """
        node_data = {
            'docker': {
                'daemon_conf': {
                    'signature-verification': False,
                },
                'all_registries': {
                    'dev': [
                        {
                            'host': 'hub-dev',
                            'insecure': True,
                        },
                        {
                            'host': 'hub-dev2',
                            'insecure': False,
                            'ca_cert': '/etc/foo.crt',
                        }
                    ],
                    'qa': [
                        {
                            'host': 'hub-qa'
                        },
                    ],
                    'prod': [
                        {
                            'host': 'hub',
                            'ca_cert': 'xxx',
                            'client_cert': 'xxx',
                            'client_key': 'xxx',
                        },
                    ],

                }
            }
        }

        self.assertEqual(
            dockerutils.get_conf('dev', node_data),
            {
                'daemon_conf': {
                    'signature-verification': False,
                },
                'registries': [
                    {
                        'host': 'hub-dev',
                        'insecure': True,
                    },
                    {
                        'host': 'hub-dev2',
                        'insecure': False,
                        'ca_cert': '/etc/foo.crt',
                    },
                ]
            }
        )

    @mock.patch('json.dump', mock.Mock())
    @mock.patch('treadmill.subproc.resolve', mock.Mock(return_value='t_runc'))
    def test__prepare_daemon_conf(self):
        """Test docker daemon conf generation.
        """
        # pylint: disable=protected-access

        mopen = mock.mock_open()
        with mock.patch('treadmill.dockerutils.open', mopen):
            dockerutils._prepare_daemon_conf('/foo', {})

        mopen.assert_called_with('/foo/daemon.json', 'w')
        json.dump.assert_called_with(
            {
                'authorization-plugins': ['authz'],
                'bridge': 'none',
                'cgroup-parent': 'docker',
                'default-runtime': 'docker-runc',
                'exec-opt': ['native.cgroupdriver=cgroupfs'],
                'hosts': ['tcp://127.0.0.1:2375'],
                'ip-forward': False,
                'ip-masq': False,
                'iptables': False,
                'ipv6': False,
                'runtimes': {
                    'docker-runc': {
                        'path': 't_runc'
                    },
                },
            },
            fp=mopen.return_value
        )

    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.fs.symlink_safe', mock.Mock())
    def test__prepare_certs(self):
        """Test docker config dir setup.
        """
        # pylint: disable=protected-access

        dockerutils._prepare_certs('/foo', [])

        registries = [
            {
                'host': 'hub1',
                'insecure': True,
            },
            {
                'host': 'hub2',
                'insecure': False,
                'ca_cert': '/etc/foo.crt',
            },
            {
                'host': 'hub3'
            },
            {
                'host': 'hub4',
                'ca_cert': 'xxx.crt',
                'client_cert': 'xxx.cert',
                'client_key': 'xxx.key',
            },
        ]

        dockerutils._prepare_certs('/foo', registries)
        treadmill.fs.mkdir_safe.assert_has_calls(
            [
                mock.call('/foo/certs.d/hub2'),
                mock.call('/foo/certs.d/hub3'),
                mock.call('/foo/certs.d/hub4'),
            ],
            any_order=True
        )
        treadmill.fs.symlink_safe.assert_has_calls(
            [
                mock.call('/foo/certs.d/hub2/ca.crt', '/etc/foo.crt'),
                mock.call('/foo/certs.d/hub4/ca.crt', 'xxx.crt'),
                mock.call('/foo/certs.d/hub4/client.cert', 'xxx.cert'),
                mock.call('/foo/certs.d/hub4/client.key', 'xxx.key'),
            ],
            any_order=True
        )


if __name__ == '__main__':
    unittest.main()
