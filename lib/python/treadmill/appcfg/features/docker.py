"""Configures dockerd inside the container."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import socket

from treadmill import dockerutils
from treadmill import nodedata
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
            _generate_dockerd_service(self._tm_env)
        )
        manifest['services'].append(
            _generate_docker_authz_service()
        )
        manifest['environ'].append(
            {'name': 'DOCKER_HOST', 'value': 'tcp://127.0.0.1:2375'}
        )
        manifest['docker'] = True


def _generate_docker_authz_service():

    # full command include creating rest module cfg file and launch sproc
    cmd = (
        'exec $TREADMILL/bin/treadmill'
        ' sproc restapi'
        ' -m docker_authz.authzreq,docker_authz.authzres,docker_authz.activate'
        ' --cors-origin=".*"'
        ' -s {sock}'
    ).format(
        sock='/run/docker/plugins/authz.sock',
    )

    docker_authz_svc = {
        'name': 'docker-auth',
        'proid': 'root',
        'restart': {
            'limit': 5,
            'interval': 60,
        },
        'command': cmd,
        'root': True,
        'environ': [],
        'config': None,
        'downed': False,
        'trace': False,
    }
    return docker_authz_svc


def _generate_dockerd_service(tm_env):
    """Configure docker daemon services."""
    # add dockerd service
    ulimits = dockerutils.init_ulimit()
    default_ulimit = dockerutils.fmt_ulimit_to_flag(ulimits)

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
        ' --block-registry="*"'
        ' {default_ulimit}'
    ).format(
        dockerd=subproc.resolve('dockerd'),
        docker_runtime=subproc.resolve('docker_runtime'),
        default_ulimit=default_ulimit,
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
        'environ': [],
        'config': None,
        'downed': False,
        'trace': False,
    }
    return dockerd_svc


def _get_docker_registry(tm_env):
    """Return the registry to use.
    """
    # get registry address from node.json
    data = nodedata.get(tm_env.configs_dir)
    registries = data['docker_registries']

    for registry in registries:
        if ':' in registry:
            host, _sep, port = registry.partition(':')
        else:
            host = registry
            port = '5000'

        # Ensure we have teh FQDN for the registry host.
        host = socket.getfqdn(host)
        yield ':'.join([host, port])
