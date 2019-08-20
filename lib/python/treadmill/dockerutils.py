"""Docker configuration helper functions.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging
import os

from treadmill import fs
from treadmill import utils
from treadmill import subproc

_LOGGER = logging.getLogger(__name__)

_DEFAULT_ULIMIT = (
    'core',
    'data',
    'fsize',
    'nofile',
    'nproc',
    'rss',
    'stack'
)


def get_conf(env, node_data):
    """Extract docker configuration from the node data.

    The expected node_dafa docker config looks like this:

      docker:
        daemon_conf:
          signature-verification: false
          debug: true
        all_registries:
          dev:
          - host: hub-dev.domain
            insecure: true
          qa:
          - host: hub-qa.domain
            insecure: true
          uat:
          - host: hub-uat.domain
            insecure: false
            ca_cert: xxx
            client_cert: xxx
            client_key: xxx
          - host: hub-uat2.domain
            insecure: true
          prod:
          - host: hub.domain
            ca_cert: xxx
            client_cert: xxx
            client_key: xxx

    the `daemon_conf` is used as docker daemon configuration
    https://docs.docker.com/engine/reference/
        commandline/dockerd/#daemon-configuration-file

    or (backward compatibility):

      docker_registries:
      - foo.domain
      - bar.domain

    or (backward compatibility):

      docker_registries:
        dev:
        - hub-dev.domain
        qa:
        - hub-qa.domain
        uat:
        - hub-uat.domain
        prod:
        - hub.domain

    The returned docker config looks like this:

        {
          daemon_conf:
            signature-verification: False
            debug: true
          registries:
            - host: hub-uat.domain
              insecure: false
              ca_cert: xxx
              client_cert: xxx
              client_key: xxx
            - host: hub-uat2.domain
              insecure: true
        }

    """
    docker_conf = node_data.get('docker', {})
    default_regs = []

    if not docker_conf and 'docker_registries' in node_data:
        # Legacy configs support
        registry_conf = node_data['docker_registries']

        if isinstance(registry_conf, list):
            # Assume we want the same registries in all environments. We do
            # this by making the list the fallback default.
            registries = {}
            default_regs = [
                {
                    'host': registry,
                    'insecure': True
                }
                for registry in list(registry_conf)
            ]

        else:
            # If the conf is a dict, ensure it has all necessary keys
            registries = {
                env: [
                    {
                        'host': registry,
                        'insecure': True,
                    }
                    for registry in registries
                ]
                for env, registries in registry_conf.items()
            }

        docker_conf = {
            'daemon_conf': {},
            'all_registries': registries,
        }
    else:
        # Normalize
        docker_conf = {
            'daemon_conf': docker_conf.get('daemon_conf', {}),
            'all_registries': docker_conf.get('all_registries', {}),
        }

    return {
        'daemon_conf': docker_conf['daemon_conf'],
        'registries': docker_conf['all_registries'].get(env, default_regs),
    }


def get_ulimits():
    """Initialize dockerd ulimits to parent process ulimit defaults.

    :returns:
        ``list(dict)`` -- List of {'Name', 'Soft', 'Hard'} resource usage
                          limits for the container.
    """
    total_result = []

    for u_type in _DEFAULT_ULIMIT:
        (soft_limit, hard_limit) = utils.get_ulimit(u_type)
        total_result.append(
            {'Name': u_type, 'Soft': soft_limit, 'Hard': hard_limit}
        )

    return total_result


def prepare_docker_confdir(docker_confdir, app, node_data):
    """prepare docker runtime environment
    """
    env = app.environment
    config = get_conf(env, node_data)

    _prepare_daemon_conf(docker_confdir, config['daemon_conf'])
    _prepare_certs(docker_confdir, config['registries'])


def _prepare_daemon_conf(confdir, daemon_conf):
    """Write down a dockerd `daemon.json` config file.
    """
    conf = {
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
                'path': subproc.resolve('docker_runtime'),
            },
        },
    }
    conf.update(daemon_conf)

    with open(os.path.join(confdir, 'daemon.json'), 'w') as f:
        json.dump(conf, fp=f)


def _prepare_certs(confdir, registries):
    """prepare certficate for docker daemon
    """
    certs_dir = os.path.join(confdir, 'certs.d')

    for registry in registries:
        if registry.get('insecure', False):
            continue

        cert_dir = os.path.join(certs_dir, registry['host'])
        fs.mkdir_safe(cert_dir)

        # symlink ca/cert/key in /etc dir
        if 'ca_cert' in registry:
            fs.symlink_safe(
                os.path.join(cert_dir, 'ca.crt'),
                registry['ca_cert']
            )
        if 'client_cert' in registry:
            fs.symlink_safe(
                os.path.join(cert_dir, 'client.cert'),
                registry['client_cert']
            )
        if 'client_key' in registry:
            fs.symlink_safe(
                os.path.join(cert_dir, 'client.key'),
                registry['client_key']
            )


__all__ = (
    'get_conf',
    'get_ulimits',
    'prepare_docker_confdir',
)
