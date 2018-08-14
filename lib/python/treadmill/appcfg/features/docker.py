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
        # TODO: we need to move dockerd and docker authz to system-services
        # when they are stable

        manifest['services'].append(
            _generate_dockerd_service(manifest, self._tm_env)
        )
        manifest['services'].append(
            _generate_docker_authz_service(manifest, self._tm_env)
        )
        manifest['environ'].append(
            {'name': 'DOCKER_HOST', 'value': 'tcp://127.0.0.1:2375'}
        )
        manifest['docker'] = True


def _generate_docker_authz_service(manifest, _tm_env):
    docker_authz_svc = {
        'name': 'docker-auth',
        'proid': 'root',
        'restart': {
            'limit': 5,
            'interval': 60,
        },
        'command': (
            'exec $TREADMILL/bin/treadmill'
            ' sproc docker-authz --user {user}'
        ).format(
            user=manifest['proid']
        ),
        'root': True,
        'environ': [],
        'config': None,
        'downed': False,
        'trace': False,
    }
    return docker_authz_svc


def _generate_dockerd_service(manifest, tm_env):
    """Configure docker daemon services."""
    # add dockerd service
    (_uid, proid_gid) = _get_user_uid_gid(manifest['proid'])

    # we disable advanced network features
    command = (
        'exec'
        ' {dockerd}'
        ' -H tcp://127.0.0.1:2375'
        ' --authorization-plugin=authz'
        ' --add-runtime docker-runc={docker_runtime}'
        ' --default-runtime=docker-runc'
        ' --exec-opt native.cgroupdriver=cgroupfs'
        ' --bridge=none'
        ' --ip-forward=false'
        ' --ip-masq=false'
        ' --iptables=false'
        ' --cgroup-parent=docker'
        ' -G {gid}'
        ' --block-registry="*"'
    ).format(
        dockerd=subproc.resolve('dockerd'),
        docker_runtime=subproc.resolve('docker_runtime'),
        gid=proid_gid,
    )

    # we only allow pull image from specified registry
    for registry_name in _get_docker_registry(tm_env):
        command += (
            ' --insecure-registry {registry}'
            ' --add-registry {registry}'
        ).format(registry=registry_name)

    dockerd_svc = {
        'name': 'dockerd',
        'proid': 'root',
        'restart': {
            'limit': 5,
            'interval': 60,
        },
        'command': command,
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
    registries = cell_config.data['docker_registries']

    for registry in registries:
        if ':' in registry:
            host, _sep, port = registry.partition(':')
        else:
            host = registry
            port = '5000'

        # Ensure we have teh FQDN for the registry host.
        host = socket.getfqdn(host)
        yield ':'.join([host, port])
