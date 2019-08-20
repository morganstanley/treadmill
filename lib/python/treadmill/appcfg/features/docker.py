"""Configures dockerd inside the container.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

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

        # get registry address from node.json
        node_data = nodedata.get(self._tm_env.configs_dir)
        docker_conf = dockerutils.get_conf(manifest['environment'],
                                           node_data)

        manifest['services'].append(
            _generate_dockerd_service(docker_conf)
        )
        manifest['services'].append(
            _generate_docker_authz_service(docker_conf)
        )
        manifest['environ'].append(
            {'name': 'DOCKER_HOST', 'value': 'tcp://127.0.0.1:2375'}
        )
        manifest['docker'] = True


def _generate_docker_authz_service(_docker_cfg):

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


def _generate_dockerd_service(docker_cfg):
    """Configure docker daemon services."""
    # add dockerd service
    # we disable advanced network features
    command = 'exec {dockerd}'.format(
        dockerd=subproc.resolve('dockerd')
    )
    extra_cmd_params = ['']  # Start with a space

    # configure ulimits.
    ulimits = dockerutils.get_ulimits()
    # Format rich dictionary to dockerd-compatible cli flags.
    # Do not respect "soft" limit as dockerd has a known issue when comparing
    # finite vs infinite values; will error on {Soft=0, Hard=-1}
    for flag in ulimits:
        extra_cmd_params.append('--default-ulimit')
        extra_cmd_params.append('{}={}:{}'.format(flag['Name'],
                                                  flag['Hard'],
                                                  flag['Hard']))

    # We block all registries and only allow image pulls from our configured
    # registries.
    extra_cmd_params.append('--block-registry="*"')
    for registry in docker_cfg['registries']:
        extra_cmd_params.append('--add-registry')
        extra_cmd_params.append(registry['host'])

        if registry.get('insecure', False):
            extra_cmd_params.append('--insecure-registry')
            extra_cmd_params.append(registry['host'])

    command += ' '.join(extra_cmd_params)
    _LOGGER.info('dockerd cmd: %s', command)

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


__all__ = (
    'DockerdFeature',
)
