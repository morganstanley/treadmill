"""Docker Sproc
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import socket
import sys
import time

from urllib.parse import urlparse

import click
import docker
import requests
import six

from treadmill import cli
from treadmill import dockerutils
from treadmill import exc
from treadmill import utils
from treadmill import supervisor

from treadmill.appcfg import abort as app_abort

_LOGGER = logging.getLogger(__name__)

# wait for dockerd is ready in seconds
_MAX_WAIT = 64


def _read_environ(envdirs):
    """Read a list of environ directories and return a full envrion ``dict``.

    :returns:
        ``dict`` - Environ dictionary.
    """
    environ = {}
    for envdir in envdirs:
        environ.update(supervisor.read_environ_dir(envdir))

    return environ


def _get_image_user(image_attrs):
    """User is in Config data
    """
    config = image_attrs.get('Config', {})
    return config.get('User', None)


def _pull_image(client, image_name):
    """Pull image from registry
    """
    # we intentionally check if image exist so that
    # we can explictly have pull image event in treadmill trace in the future
    try:
        image_meta = client.images.get(image_name)
        # TODO: send image in place event
    except docker.errors.ImageNotFound:
        image_meta = client.images.pull(image_name)
        # TODO: pull image event

    return image_meta


def _load_image(client, load):
    """Load image from local disk
    """
    with open(load, 'rb') as f:
        # load returns image list
        return client.images.load(data=f)[0]


def _create_container(client, name, image_meta,
                      entrypoint, cmd, ulimit, **args):
    """Create docker container from given app.
    """
    # if success,  pull returns an image object
    container_args = {
        'name': name,
        'image': image_meta.id,
        'command': cmd,
        'entrypoint': entrypoint,
        'detach': True,
        'stdin_open': True,
        'tty': True,
        'network_mode': 'host',
        'pid_mode': 'host',
        'ipc_mode': 'host',
        'ulimits': ulimit,
        # XXX: uts mode not supported by python lib yet
        # 'uts_mode': 'host',
    }

    # assign user argument
    user = _get_image_user(image_meta.attrs)
    if user is None or user == '':
        uid = os.getuid()
        gid = os.getgid()
        container_args['user'] = '{}:{}'.format(uid, gid)

    # add additonal container args
    for key, value in six.iteritems(args):
        if value is not None:
            container_args[key] = value

    try:
        # The container might exist already
        container = client.containers.get(name)
        container.remove(force=True)
        # TODO: remove container event
    except docker.errors.NotFound:
        pass
    except docker.errors.APIError as err:
        raise exc.ContainerSetupError(
            'Fail to remove container {}: {}'.format(name, err),
            app_abort.AbortedReason.PRESENCE
        )

    _LOGGER.info('Run docker: %r', container_args)
    return client.containers.create(**container_args)


def _transform_volumes(volumes):
    """Transform volume mapping from list to dict regconized by docker lib
    """
    dict_volume = {}
    for volume in volumes:
        # Example format:
        #   /var/tmp:/dest_var_tmp:rw => {
        #       /var/tmp': {
        #           'bind': '/dest_var_tmp',
        #           'mode': 'rw
        #       }
        #   }
        (target, source, mode) = volume.split(':', 2)
        dict_volume[target] = {'bind': source, 'mode': mode}

    return dict_volume


def _parse_image_name(image):
    """Parse image name from manifest
    """
    url = urlparse(image)

    scheme = url.scheme if url.scheme else 'docker'
    path = url.path

    if url.netloc:
        path = url.netloc + path

    # change /meta/proj => meta/proj
    if scheme == 'docker' and path[0] == '/':
        path = path[1:]

    return (scheme, path)


def _fetch_image(client, image):
    """Fetch image from local file or registry
    returns image metadata object
    """
    (scheme, path) = _parse_image_name(image)

    if scheme == 'file':
        try:
            image_meta = _load_image(client, path)
        except docker.errors.ImageNotFound:
            raise exc.ContainerSetupError(
                'Failed to load image file {}'.format(image),
                app_abort.AbortedReason.IMAGE
            )
    elif scheme == 'docker':
        # simulate docker pull logic, if tag not provided, assume latest
        if ':' not in path:
            path += ':latest'

        try:
            image_meta = _pull_image(client, path)
        except docker.errors.ImageNotFound:
            raise exc.ContainerSetupError(
                'Fail to pull {}, check image name or disk size'.format(
                    image
                ),
                app_abort.AbortedReason.IMAGE
            )
    else:
        raise exc.ContainerSetupError(
            'Unrecognized image name {}'.format(image),
            app_abort.AbortedReason.IMAGE
        )

    return image_meta


class DockerSprocClient:
    """Docker Treadmill Sproc client
    """

    __slots__ = (
        'client',
        'param',
        'tm_env',
    )

    def __init__(self, param=None):
        self.client = None
        if param is None:
            self.param = {}
        else:
            self.param = param

    def _get_client(self):
        """Gets the docker client.
        """
        if self.client is not None:
            return self.client

        self.client = docker.from_env(**self.param)

        self._wait_client_ready(self.client)

        return self.client

    def run(self, name, image, entrypoint, cmd, **args):
        """Load Docker image and Run
        """
        client = self._get_client()
        if 'volumes' in args:
            args['volumes'] = _transform_volumes(args['volumes'])

        if 'envdirs' in args:
            args['environment'] = _read_environ(args.pop('envdirs'))

        ulimit = dockerutils.init_ulimit(args.pop('ulimit'))

        image_meta = _fetch_image(client, image)

        container = _create_container(
            client, name, image_meta, entrypoint, cmd, ulimit, **args
        )

        # TODO: start docker container event
        container.start()

        container.reload()
        logs_gen = container.logs(
            stdout=True,
            stderr=True,
            stream=True,
            follow=True
        )

        _LOGGER.info('Container %s is running', name)
        while container.status == 'running':
            try:
                for log_lines in logs_gen:
                    print(log_lines, file=sys.stderr, end='', flush=True)
            except socket.error:
                pass

            container.reload()

        # container.wait returns dict with key 'StatusCode'
        rc = container.wait()['StatusCode']
        if os.WIFSIGNALED(rc):
            # Process died with a signal in docker
            sig = os.WTERMSIG(rc)
            os.kill(os.getpid(), sig)

        else:
            utils.sys_exit(os.WEXITSTATUS(rc))

    @staticmethod
    def _wait_client_ready(client):
        """wait for dockerd ready
        """
        wait = 1
        while True:
            try:
                client.ping()
                break
            except requests.exceptions.ConnectionError as err:
                # if wait too long, we quit current process
                if wait > _MAX_WAIT:
                    raise err
                _LOGGER.info('Dockerd not ready, wait %ds', wait)
                time.sleep(wait)
                wait *= 2


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--name', required=True, help='name of container')
    @click.option('--image', required=True, help='container image')
    @click.argument('cmd', nargs=-1)
    @click.option('--entrypoint', required=False, help='Entrypoint')
    @click.option('--user', required=False,
                  help='userid in the form UID:GID')
    @click.option('--envdirs', type=cli.LIST, required=False, default='',
                  help='List of environ directory to pass into the container.')
    @click.option('--read-only', is_flag=True, default=False,
                  help='Mount the docker image read-only')
    @click.option('--volume', multiple=True, required=False,
                  help='Specify each volume as TARGET:SOURCE:MODE')
    @click.option('--ulimit', multiple=True, required=False,
                  help='Specify ulimit value as TYPE:SOFT_LIMIT:HARD_LIMIT')
    def configure(name, image, cmd, entrypoint,
                  user, envdirs, read_only, volume, ulimit):
        """Configure local manifest and schedule app to run."""
        # client do not timeout
        param = {'timeout': None}
        service_client = DockerSprocClient(param)
        service_client.run(
            # manditory parameters
            name, image, entrypoint, cmd,
            # optional parameters
            user=user,
            envdirs=envdirs,
            read_only=read_only,
            volumes=volume,
            ulimit=ulimit,
        )

    return configure
