"""manifest module for linux runtime
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import shlex

from treadmill import subproc
from treadmill.appcfg import manifest as app_manifest

_LOGGER = logging.getLogger(__name__)

TREADMILL_BIND_PATH = '/opt/treadmill-bind'


def add_runtime(tm_env, manifest):
    """Adds linux (docker) runtime specific details to the manifest.
    """
    dockers = _transform_services(manifest)

    app_manifest.add_linux_system_services(tm_env, manifest)
    app_manifest.add_linux_services(manifest)


def _generate_command(service):
    """Get treadmill docker running command from image
    """
    is_docker = False
    if 'image' in service:
        cmd = _get_docker_run_cmd(
            service['name'],
            service['image'],
            service.get('args', None),
            service.get('command', None)
        )
        is_docker = True
    else:
        cmd = service['command']

    return (cmd, is_docker)


def _get_docker_run_cmd(name, image,
                        args=None, command=None, uidgid=None):
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
        'exec $TREADMILL/bin/treadmill sproc docker'
        ' --name {name}'
        ' --envdirs /env,/docker/env,/services/{name}/env'
    )

    for volume in volumes:
        tpl += ' --volume {source}:{dest}:{mode}'.format(
            source=volume[0],
            dest=volume[1],
            mode=volume[2]
        )

    if uidgid is not None:
        tpl += ' --user {uidgid}'.format(uidgid=uidgid)

    # put entrypoint and image in the last
    if command is not None:
        tpl += ' --entrypoint {entrypoint}'
        command = shlex.quote(command)

    tpl += ' --image {image}'

    # create args str in treadmill sproc docker
    if args is not None:
        tpl += ' -- {cmd}'
        args_str = ' '.join([shlex.quote(arg) for arg in args])
    else:
        args_str = None

    return tpl.format(
        name=name,
        image=image,
        entrypoint=command,
        cmd=args_str,
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
        (cmd, is_docker) = _generate_command(service)

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
                'downed': service.get('downed', False),
                'trace': True,
                'logger': service.get('logger', 's6.app-logger.run'),
            }
        )

    manifest['services'] = services
    return dockers
