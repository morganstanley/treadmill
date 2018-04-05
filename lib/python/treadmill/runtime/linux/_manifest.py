"""manifest module for linux runtime
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import pwd
import socket
import sys

from treadmill import subproc

from treadmill.appcfg import manifest as app_manifest

_LOGGER = logging.getLogger(__name__)

TREADMILL_BIND_PATH = '/opt/treadmill-bind'


def add_runtime(tm_env, manifest):
    """Adds linux runtime specific details to the manifest.
    And add docker runtime specific details to the manifest
    """
    dockers = _transform_services(manifest)

    app_manifest.add_linux_system_services(tm_env, manifest)
    app_manifest.add_linux_services(manifest)

    if dockers:
        _add_dockerd_services(manifest, tm_env)
        manifest['docker'] = True
    else:
        manifest['docker'] = False


def _generate_command(name, raw_cmd):
    """Get treadmill docker running command from image
    """
    is_docker = False
    if raw_cmd.startswith('docker://'):
        image_cmd = raw_cmd[9:].split(None, 1)
        if len(image_cmd) > 1:
            image = image_cmd[0]
            cmd = image_cmd[1]
        else:
            image = image_cmd[0]
            cmd = None
        cmd = _get_docker_run_cmd(name, image, cmd)
        is_docker = True
    else:
        cmd = raw_cmd

    return (cmd, is_docker)


def _get_docker_run_cmd(name, image, command=None, uidgid=None):
    """Get docker run cmd from raw command
    """
    # TODO: hardode volume for now

    treadmill_bind = subproc.resolve('treadmill_bind_distro')

    # XXX: hardode volume for now
    volumes = [
        ('/var/tmp', '/var/tmp', 'rw'),
        ('/var/spool', '/var/spool', 'rw'),
        ('/docker/etc/hosts', '/etc/hosts', 'ro'),
        ('/env', '/env', 'ro'),
        (treadmill_bind, TREADMILL_BIND_PATH, 'ro'),
    ]

    tpl = (
        'exec {python} -m treadmill sproc'
        ' docker'
        ' --name {name}'
        ' --envdirs /env,/docker/env,/services/{name}/env'
        ' --image {image}'
    )

    for volume in volumes:
        tpl += ' --volume {source}:{dest}:{mode}'.format(
            source=volume[0],
            dest=volume[1],
            mode=volume[2]
        )

    if uidgid is not None:
        tpl += ' --user {uidgid}'.format(uidgid=uidgid)

    if command is not None:
        tpl += ' -- {cmd}'

    return tpl.format(
        python=sys.executable,
        name=name,
        image=image,
        cmd=command,
    )


def _transform_services(manifest):
    """Adds linux runtime specific details to the manifest.
    returns:
        int -- number of docker services in the manifest
    """
    dockers = 0

    # Normalize restart count
    services = []
    for service in manifest.get('services', []):
        (cmd,
         is_docker) = _generate_command(service['name'], service['command'])

        if is_docker:
            dockers += 1

        services.append(
            {
                'name': service['name'],
                'command': cmd,
                'restart': {
                    'limit': int(service['restart']['limit']),
                    'interval': int(service['restart']['interval']),
                },
                'root': service.get('root', False),
                'proid': (
                    'root' if service.get('root', False)
                    else manifest['proid']
                ),
                'environ': manifest['environ'],
                'config': None,
                'downed': False,
                'trace': True,
                'logger': service.get('logger', 's6.app-logger.run'),
            }
        )

    manifest['services'] = services
    return dockers


def _get_docker_registry(_tm_env):
    """Return the registry to use.
    """
    # TODO get registry from cell_config.yml
    registry = 'lab-repo.msdev.ms.com:5000'
    if ':' in registry:
        host, _sep, port = registry.partition(':')
    else:
        host = registry
        port = 5000

    # Ensure we have teh FQDN for the registry host.
    host = socket.getfqdn(host)
    return ':'.join([host, port])


def _add_dockerd_services(manifest, tm_env):
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
            ' --add-runtime docker-runc={docker_runtime}'
            ' --default-runtime=docker-runc'
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
            docker_runtime=subproc.resolve('docker_runtime'),
            gid=proid_gid,
            registry=_get_docker_registry(tm_env)
        ),
        'root': True,
        'environ': [
            {'name': 'DOCKER_RAMDISK', 'value': '1'},
        ],
        'config': None,
        'downed': False,
        'trace': False,
    }
    manifest['services'].append(dockerd_svc)


def _get_user_uid_gid(username):
    user_pw = pwd.getpwnam(username)
    return (user_pw.pw_uid, user_pw.pw_gid)
