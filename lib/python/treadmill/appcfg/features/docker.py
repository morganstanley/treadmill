"""Configures dockerd inside the container."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import pwd
import socket

from treadmill import cellconfig
from treadmill import subproc
from treadmill.appcfg.features import feature_base

_LOGGER = logging.getLogger(__name__)


class DockerdFeature(feature_base.Feature):
    """Feature to enabled docker daemon in container
    """

    def applies(self, manifest, runtime):
        return runtime == 'linux'

    def configure(self, manifest):
        _LOGGER.info('Configuring dockerd.')

        manifest['services'].append(
            _generate_dockerd_service(manifest, self._tm_env)
        )
        manifest['docker'] = True


def _generate_dockerd_service(manifest, tm_env):
    """Configure docker daemon services."""
    # add dockerd service
    (_uid, proid_gid) = _get_user_uid_gid(manifest['proid'])
    dockerd_svc = {
        'name': 'dockerd',
        'proid': 'root',
        'restart': {
            'limit': 5,
            'interval': 60,
        },
        'command': (
            'exec {dockerd}'
            ' --exec-opt native.cgroupdriver=cgroupfs'
            ' --bridge=none'
            ' --ip-forward=false'
            ' --ip-masq=false'
            ' --iptables=false'
            ' --cgroup-parent=docker'
            ' -G {gid}'
            ' --insecure-registry {registry}'
            ' --add-registry {registry}'
        ).format(
            dockerd=subproc.resolve('dockerd'),
            gid=proid_gid,
            registry=_get_docker_registry(tm_env),
        ),
        'root': True,
        'environ': [
            {'name': 'DOCKER_RAMDISK', 'value': '1'},
        ],
        'config': None,
        'downed': False,
        'trace': False,
    }
    return dockerd_svc


def _get_user_uid_gid(username):
    user_pw = pwd.getpwnam(username)
    return (user_pw.pw_uid, user_pw.pw_gid)


def _get_docker_registry(tm_env):
    """Return the registry to use.
    """
    # get registry address from cell_config.yml
    cell_config = cellconfig.CellConfig(tm_env.root)
    registry = cell_config.data['docker_registry']

    if ':' in registry:
        host, _sep, port = registry.partition(':')
    else:
        host = registry
        port = '5000'

    # Ensure we have teh FQDN for the registry host.
    host = socket.getfqdn(host)
    return ':'.join([host, port])
