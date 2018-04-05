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

import click
import docker
import six

from treadmill import cli
from treadmill import exc
from treadmill import utils
from treadmill import supervisor

from treadmill.appcfg import abort as app_abort

_LOGGER = logging.getLogger(__name__)


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


def _create_container(client, name, image_name, cmd, **args):
    """Create docker container from given app.
    """
    # if success,  pull returns an image object
    image = client.images.pull(image_name)

    container_args = {
        'name': name,
        'image': image_name,
        'command': list(cmd),
        'detach': True,
        'stdin_open': True,
        'tty': True,
        'network_mode': 'host',
        'pid_mode': 'host',
        'ipc_mode': 'host',
        # XXX: uts mode not supported by python lib yet
        # 'uts_mode': 'host',
    }

    # assign user argument
    user = _get_image_user(image.attrs)
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
        # TODO: start existing container with different ports
        container = client.containers.get(name)
        container.remove(force=True)
    except docker.errors.NotFound:
        pass

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


class DockerSprocClient(object):
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

        # wait for dockerd ready
        time.sleep(1)

    def _get_client(self):
        """Gets the docker client.
        """
        if self.client is not None:
            return self.client

        self.client = docker.from_env(**self.param)
        return self.client

    def run(self, name, image, cmd, **args):
        """Run
        """
        client = self._get_client()
        try:
            if 'volumes' in args:
                args['volumes'] = _transform_volumes(args['volumes'])

            if 'envdirs' in args:
                args['environment'] = _read_environ(args.pop('envdirs'))

            container = _create_container(
                client, name, image, cmd, **args
            )

        except docker.errors.ImageNotFound:
            raise exc.ContainerSetupError(
                'Image {0} was not found'.format(image),
                app_abort.AbortedReason.IMAGE
            )

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
                    sys.stderr.write(log_lines)
            except socket.error:
                pass

            container.reload()

        rc = container.wait()
        if os.WIFSIGNALED(rc):
            # Process died with a signal in docker
            sig = os.WTERMSIG(rc)
            os.kill(os.getpid(), sig)

        else:
            utils.sys_exit(os.WEXITSTATUS(rc))


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--name', required=True, help='name of container')
    @click.option('--image', required=True, help='container image')
    @click.argument('cmd', nargs=-1)
    @click.option('--user', required=False,
                  help='userid in the form UID:GID')
    @click.option('--envdirs', type=cli.LIST, required=False, default='',
                  help='List of environ directory to pass into the container.')
    @click.option('--read-only', is_flag=True, default=False,
                  help='Mount the docker image read-only')
    @click.option('--volume', multiple=True, required=False,
                  help='Specify each volume as TARGET:SOURCE:MODE')
    def configure(name, image, cmd, user, envdirs, read_only, volume):
        """Configure local manifest and schedule app to run."""
        service_client = DockerSprocClient()
        service_client.run(
            # manditory parameters
            name, image, cmd,
            # optional parameters
            user=user,
            envdirs=envdirs,
            read_only=read_only,
            volumes=volume,
        )

    return configure
