"""Docker funtion in linux runtime
"""

import grp  # pylint: disable=import-error
import io
import logging
import os

from treadmill import exc
from treadmill import fs
from treadmill import subproc
from treadmill import supervisor
from treadmill import utils

from treadmill.appcfg import abort as app_abort
from treadmill.fs import linux as fs_linux

from .. import _manifest


_LOGGER = logging.getLogger(__name__)

_CONTAINER_DOCKER_ENV_DIR = os.path.join('docker', 'env')
_CONTAINER_DOCKER_ETC_DIR = os.path.join('docker', 'etc')

_PASSWD_PATTERN = '{NAME}:x:{UID}:{GID}:{INFO}:{HOME}:{SHELL}'
_GROUP_PATTERN = '{NAME}:x:{GID}'


def _has_docker(app):
    return hasattr(app, 'docker') and app.docker


def create_docker_environ_dir(container_dir, root_dir, app):
    """Creates environ dir for docker"""
    if not _has_docker(app):
        return

    env_dir = os.path.join(container_dir, _CONTAINER_DOCKER_ENV_DIR)
    env = {}

    treadmill_bind_preload_so = os.path.basename(
        subproc.resolve('treadmill_bind_preload.so')
    )
    if app.ephemeral_ports.tcp or app.ephemeral_ports.udp:
        env['LD_PRELOAD'] = os.path.join(
            _manifest.TREADMILL_BIND_PATH,
            '$LIB',
            treadmill_bind_preload_so
        )

    supervisor.create_environ_dir(env_dir, env)

    # Bind the environ directory in the container volume
    fs.mkdir_safe(os.path.join(root_dir, _CONTAINER_DOCKER_ENV_DIR))
    fs_linux.mount_bind(
        root_dir, os.path.join(os.sep, _CONTAINER_DOCKER_ENV_DIR),
        source=os.path.join(container_dir, _CONTAINER_DOCKER_ENV_DIR),
        recursive=False, read_only=True
    )


def mount_docker_daemon_path(newroot_norm, app):
    """Mount tmpfs for docker
    """
    if not _has_docker(app):
        return

    # /etc/docker as temp fs as dockerd create /etc/docker/key.json
    try:
        fs_linux.mount_tmpfs(newroot_norm, '/etc/docker')
    except FileNotFoundError as err:
        _LOGGER.error('Failed to mount docker tmpfs: %s', err)
        # this exception is caught by sproc run to generate abort event
        raise exc.ContainerSetupError(
            msg=str(err),
            reason=app_abort.AbortedReason.UNSUPPORTED,
        )


def overlay_docker(container_dir, root_dir, app):
    """Mount etc/hosts for docker container
    """
    # FIXME: This path is mounted as RW because ro volume in treadmill
    #        container can not be mounted in docker 'Error response from
    #        daemon: chown /etc/hosts: read-only file system.'

    if not _has_docker(app):
        return

    overlay_dir = os.path.join(container_dir, 'overlay')

    fs_linux.mount_bind(
        root_dir, os.path.join(os.sep, _CONTAINER_DOCKER_ETC_DIR, 'hosts'),
        source=os.path.join(overlay_dir, 'etc/hosts'),
        recursive=False, read_only=False
    )
    _create_overlay_passwd(root_dir, app.proid)
    _create_overlay_group(root_dir, app.proid)


def _create_overlay_group(root_dir, proid):
    """create a overlay /etc/group in oder to mount into container
    """
    path = os.path.join(root_dir, _CONTAINER_DOCKER_ETC_DIR, 'group')
    (_uid, gid) = utils.get_uid_gid(proid)
    with io.open(path, 'w') as f:
        root = _GROUP_PATTERN.format(
            NAME='root',
            GID=0
        )
        f.write('{}\n'.format(root))
        group = _GROUP_PATTERN.format(
            NAME=grp.getgrgid(gid).gr_name,
            GID=gid
        )
        f.write('{}\n'.format(group))


def _create_overlay_passwd(root_dir, proid):
    """create a overlay /etc/passwd in order to mount into container
    """
    path = os.path.join(root_dir, _CONTAINER_DOCKER_ETC_DIR, 'passwd')
    (uid, gid) = utils.get_uid_gid(proid)
    with io.open(path, 'w') as f:
        root = _PASSWD_PATTERN.format(
            NAME='root',
            UID=0,
            GID=0,
            INFO='root',
            HOME='/root',
            SHELL='/bin/sh'
        )
        f.write('{}\n'.format(root))
        user = _PASSWD_PATTERN.format(
            NAME=proid,
            UID=uid,
            GID=gid,
            INFO='',
            HOME='/',
            SHELL='/sbin/nologin'
        )
        f.write('{}\n'.format(user))
