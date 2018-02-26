"""manifest module for linux runtime
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import pwd

from treadmill import dist
from treadmill import subproc

from treadmill.appcfg import manifest as app_manifest

_LOGGER = logging.getLogger(__name__)


def add_runtime(tm_env, manifest):
    """Adds linux runtime specific details to the manifest.
    And add docker runtime specific details to the manifest
    """
    _transform_services(manifest)

    app_manifest.add_linux_system_services(tm_env, manifest)
    app_manifest.add_linux_services(manifest)
    _add_dockerd_services(manifest, tm_env)


def _generate_command(raw_cmd, proid, unique_id):
    """Get treadmill docker running command from image
    """
    if raw_cmd.startswith('docker://'):
        image_cmd = raw_cmd[9:].split(None, 1)
        if len(image_cmd) > 1:
            cmd = image_cmd[1]
        else:
            cmd = None
        return _get_docker_run_cmd(proid, unique_id, image_cmd[0], cmd)
    else:
        return raw_cmd


def _get_docker_run_cmd(username, unique_id, image, command=None):
    """Get docker run cmd from raw command
    """
    (uid, gid) = _get_user_uid_gid(username)

    # XXX: hardode volume for now
    volumes = [
        ('/var/tmp', '/var/tmp', 'rw'),
        ('/var/spool', '/var/spool', 'rw'),
    ]

    tpl = (
        'exec {tm} sproc docker --unique_id {unique_id} --user {uid}:{gid}'
        ' --image {image}'
    )

    for volume in volumes:
        tpl += ' --volume {source}:{dest}:{mode}'.format(
            source=volume[0],
            dest=volume[1],
            mode=volume[2]
        )

    if command is not None:
        tpl += ' -- {cmd}'

    return tpl.format(
        tm=dist.TREADMILL_BIN,
        unique_id=unique_id,
        uid=uid,
        gid=gid,
        image=image,
        cmd=command,
    )


def _transform_services(manifest):
    """Adds linux runtime specific details to the manifest."""
    # Normalize restart count
    manifest['services'] = [
        {
            'name': service['name'],
            'command': _generate_command(
                service['command'],
                manifest['proid'],
                service['name'],
            ),
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
        }
        for service in manifest.get('services', [])
    ]


def _get_docker_registry(_tm_env):
    # TODO get registry from cell_config.yml
    return 'registry:5000'


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
            'exec {dockerd} --add-runtime docker-runc={docker_runtime}'
            ' --default-runtime=docker-runc'
            ' --exec-opt native.cgroupdriver=cgroupfs --bridge=none'
            ' --ip-forward=false --ip-masq=false --iptables=false'
            ' --cgroup-parent=/docker -G {gid}'
            ' --insecure-registry {registry} --add-registry {registry}'
        ).format(
            dockerd=subproc.resolve('dockerd'),
            docker_runtime=subproc.resolve('docker_runtime'),
            gid=proid_gid,
            registry=_get_docker_registry(tm_env)
        ),
        'root': True,
        'environ': [],
        'config': None,
        'downed': False,
        'trace': False,
    }
    manifest['services'].append(dockerd_svc)


def _get_user_uid_gid(username):
    user_pw = pwd.getpwnam(username)
    return (user_pw.pw_uid, user_pw.pw_gid)
