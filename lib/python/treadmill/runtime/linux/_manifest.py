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
    _transform_services(manifest)

    app_manifest.add_linux_system_services(tm_env, manifest)
    app_manifest.add_linux_services(manifest)


def _get_docker_run_cmd(name, image,
                        uidgid=None,
                        commands=None,
                        use_shell=True):
    """Get docker run cmd from raw command
    """
    tpl = (
        'exec $TREADMILL/bin/treadmill sproc docker'
        ' --name {name}'
        ' --envdirs /env,/docker/env,/services/{name}/env'
    )

    # FIXME: hardcode volumes for now
    treadmill_bind = subproc.resolve('treadmill_bind_distro')
    volumes = [
        ('/var/log', '/var/log', 'rw'),
        ('/var/spool', '/var/spool', 'rw'),
        ('/var/tmp', '/var/tmp', 'rw'),
        ('/docker/etc/hosts', '/etc/hosts', 'ro'),
        ('/docker/etc/passwd', '/etc/passwd', 'ro'),
        ('/docker/etc/group', '/etc/group', 'ro'),
        ('/env', '/env', 'ro'),
        (treadmill_bind, TREADMILL_BIND_PATH, 'ro'),
    ]
    for volume in volumes:
        tpl += ' --volume {source}:{dest}:{mode}'.format(
            source=volume[0],
            dest=volume[1],
            mode=volume[2]
        )

    if uidgid is not None:
        tpl += ' --user {uidgid}'.format(uidgid=uidgid)

    tpl += ' --image {image}'

    # put entrypoint and image in the last
    if commands is not None:
        commands = shlex.split(commands)
        if not use_shell:
            tpl += ' --entrypoint {entrypoint}'
            entrypoint = commands.pop(0)
        else:
            entrypoint = None
        if commands:
            tpl += ' -- {cmds}'
    else:
        commands = []
        entrypoint = None

    return tpl.format(
        name=name,
        image=image,
        entrypoint=entrypoint,
        cmds=' '.join((shlex.quote(cmd) for cmd in commands))
    )


def _transform_services(manifest):
    """Adds linux runtime specific details to the manifest.
    returns:
        int -- number of docker services in the manifest
    """
    # Normalize restart count
    services = []
    for service in manifest.get('services', []):
        if 'image' in service:
            cmd = _get_docker_run_cmd(name=service['name'],
                                      image=service['image'],
                                      commands=service.get('command', None),
                                      use_shell=service.get('useshell', False))
        else:
            # TODO: Implement use_shell=False for standard commands.
            cmd = service['command']

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
                'environ': service.get('environ', []),
                'config': None,
                'downed': service.get('downed', False),
                'trace': True,
                'logger': service.get('logger', 's6.app-logger.run'),
            }
        )

    manifest['services'] = services
