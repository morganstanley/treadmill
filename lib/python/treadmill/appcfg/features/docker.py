"""Configures dockerd inside the container."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
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
            _generate_dockerd_service(self._tm_env, manifest)
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


def _generate_dockerd_service(tm_env, manifest):
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

    tls_enabled = False
    tls_conf = _get_tls_conf(tm_env)

    if tls_conf.get('ca_cert'):
        command += (
            ' --tlsverify'
            ' --tlscacert={ca_cert}'
        ).format(
            ca_cert=tls_conf['ca_cert'],
        )
        tls_enabled = True

    if tls_conf.get('host_cert') or tls_conf.get('host_key'):
        # NOTE: host_cert/host_key come in pair.
        command += (
            ' --tlscert={host_cert}'
            ' --tlskey={host_key}'
        ).format(
            host_cert=tls_conf['host_cert'],
            host_key=tls_conf['host_key']
        )

    # we only allow pull image from specified registry
    for registry_name in _get_docker_registry(tm_env, manifest['environment']):
        command += (
            ' --add-registry {registry}'
        ).format(
            registry=registry_name
        )
        if not tls_enabled:
            command += (
                ' --insecure-registry {registry}'
            ).format(
                registry=registry_name
            )

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


def _get_tls_conf(tm_env):
    """Return the paths to the TLS certificates on the host.

    :returns:
        ``dict(ca_cert=str, host_cert=str, host_key=str)`` -- Paths to the
        CA root certificate, host certificate and host key.
        ``dict()`` -- Empty dict if key not found.
    """
    # get registry address from node.json
    data = nodedata.get(tm_env.configs_dir)
    tls_conf = data.get('tls_certs')

    if not tls_conf:
        return {}

    return {
        'ca_cert': tls_conf.get('ca_cert', ''),
        'host_cert': tls_conf.get('host_cert', ''),
        'host_key': tls_conf.get('host_key', ''),
    }


def _get_docker_registry(tm_env, app_environment):
    """Return the registry to use.
    """
    # get registry address from node.json
    data = nodedata.get(tm_env.configs_dir)
    registry_conf = data['docker_registries']
    if isinstance(registry_conf, list):
        # Backward compatibility: If the conf is a list turn in to dict
        registries = collections.defaultdict(lambda: list(registry_conf))
    else:
        # If the conf is a dict, ensure it has all necessary keys
        registries = collections.defaultdict(lambda: [])
        registries.update(registry_conf)

    for registry in registries[app_environment]:
        if ':' in registry:
            host, _sep, port = registry.partition(':')
        else:
            host = registry
            port = None

        # Ensure we have teh FQDN for the registry host.
        host = socket.getfqdn(host)
        res = [host, port] if port is not None else [host]
        yield ':'.join(res)
