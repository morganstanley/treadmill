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


def _get_name(image, unique_id):
    """Get name from image and unique_id
    """
    # TODO
    return '{}-{}'.format(image, unique_id)


def _read_environ(envdirs):
    """Read a list of environ directories and return a full envrion ``dict``.

    :returns:
        ``dict`` - Environ dictionary.
    """
    environ = {}
    for envdir in envdirs:
        environ.update(supervisor.read_environ_dir(envdir))

    return environ


def _create_container(client, image, cmd, name, **args):
    """Create docker container from given app.
    """
    client.images.pull(image)

    container_args = {
        'image': image,
        'name': name,
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

    # add additonal container args
    for key, value in six.iteritems(args):
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

    def run(self, image, cmd, unique_id, **args):
        """Run
        """
        client = self._get_client()
        try:
            name = _get_name(image, unique_id)

            if 'volumes' in args:
                args['volumes'] = _transform_volumes(args['volumes'])

            if 'envdirs' in args:
                args['environment'] = _read_environ(args.pop('envdirs'))

            container = _create_container(
                client, image, cmd, name, **args
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
    @click.option('--image', required=True, help='docker image')
    @click.option('--unique_id', required=True, help='uniq_id for container')
    @click.option('--user', required=False,
                  help='userid in the form UID:GID')
    @click.option('--envdirs', type=cli.LIST, required=False, default=[],
                  help='List of environ directory to pass into the container.')
    @click.option('--read-only', is_flag=True, default=False,
                  help='Mount the docker image read-only')
    @click.option('--volume', multiple=True, required=False,
                  help='Specify each volume as TARGET:SOURCE:MODE')
    @click.argument('cmd', nargs=-1)
    def configure(image, cmd, user, envdirs, unique_id, read_only, volume):
        """Configure local manifest and schedule app to run."""
        service_client = DockerSprocClient()
        service_client.run(
            # manditory parameters
            image, cmd, unique_id,
            # optional parameters
            user=user,
            envdirs=envdirs,
            read_only=read_only,
            volumes=volume,
        )

    return configure
