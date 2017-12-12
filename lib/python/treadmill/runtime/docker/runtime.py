"""Docker runtime interface.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import json
import logging
import multiprocessing
import os
import socket
import time

import docker

from treadmill import appcfg
from treadmill import appevents
from treadmill import context
from treadmill import exc
from treadmill import logcontext as lc
from treadmill import presence
from treadmill import runtime

from treadmill.appcfg import abort as app_abort
from treadmill.apptrace import events
from treadmill.runtime import runtime_base

if os.name == 'nt':
    from treadmill.ad import gmsa
    from treadmill.ad import credential_spec


_LOGGER = logging.getLogger(__name__)


def _create_environ(app):
    """Creates environ object.
    """
    appenv = {envvar.name: envvar.value for envvar in app.environ}

    appenv.update({
        'TREADMILL_CPU': app.cpu,
        'TREADMILL_DISK': app.disk,
        'TREADMILL_MEMORY': app.memory,
        'TREADMILL_CELL': app.cell,
        'TREADMILL_APP': app.app,
        'TREADMILL_INSTANCEID': app.task,
        'TREADMILL_IDENTITY': app.identity,
        'TREADMILL_IDENTITY_GROUP': app.identity_group,
        'TREADMILL_PROID': app.proid,
        'TREADMILL_ENV': app.environment,
        'TREADMILL_HOSTNAME': socket.getfqdn().lower()
    })

    for endpoint in app.endpoints:
        envname = 'TREADMILL_ENDPOINT_{0}'.format(endpoint.name.upper())
        appenv[envname] = str(endpoint.real_port)

    appenv['TREADMILL_EPHEMERAL_TCP_PORTS'] = ' '.join(
        [str(port) for port in app.ephemeral_ports.tcp]
    )
    appenv['TREADMILL_EPHEMERAL_UDP_PORTS'] = ' '.join(
        [str(port) for port in app.ephemeral_ports.udp]
    )

    return appenv


def _get_gmsa(tm_env, client, app, container_args):
    """Waits on GMSA details and adds the credential spec to the args.
    """
    check = gmsa.HostGroupCheck(tm_env)

    count = 0
    found = False
    while count < 60:
        found = check.host_in_proid_group(app.proid)

        if found:
            break

        count += 1
        time.sleep(1000)

    if not found:
        raise exc.ContainerSetupError(
            'Image {0} was not found'.format(app.image),
            app_abort.AbortedReason.GMSA
        )

    path = credential_spec.generate(app.proid, container_args['name'], client)

    container_args['security_opt'] = [
        'credentialspec={}'.format(path)
    ]
    container_args['hostname'] = app.proid


def _create_container(tm_env, client, app):
    """Create docker container from given app.
    """
    ports = {}
    for endpoint in app.endpoints:
        port_key = '{0}/{1}'.format(endpoint.port, endpoint.proto)
        ports[port_key] = endpoint.real_port

    # app.image contains a uri which starts with docker://
    image_name = app.image[9:]
    client.images.pull(image_name)

    name = appcfg.app_unique_name(app)

    container_args = {
        'image': image_name,
        'name': name,
        'environment': _create_environ(app),
        'entrypoint': app.command,
        'command': app.args,
        'detach': True,
        'tty': True,
        'ports': ports,
        'network': 'nat',
        # 1024 is max number of shares for docker
        'cpu_shares': int(
            (app.cpu / (multiprocessing.cpu_count() * 100.0)) * 1024),
        'mem_limit': app.memory,
        'storage_opt': {
            'size': app.disk
        }
    }

    if os.name == 'nt':
        _get_gmsa(tm_env, client, app, container_args)

    try:
        # The container might exist already
        # TODO: start existing container with different ports
        container = client.containers.get(name)
        container.remove(force=True)
    except docker.errors.NotFound:
        pass

    return client.containers.create(**container_args)


def _check_aborted(container_dir):
    """check if app was aborted and why.
    """
    aborted = None

    aborted_file = os.path.join(container_dir, 'aborted')
    try:
        with io.open(aborted_file) as f:
            aborted = json.load(f)

    except IOError:
        _LOGGER.debug('aborted file does not exist: %r', aborted_file)

    return aborted


class DockerRuntime(runtime_base.RuntimeBase):
    """Docker Treadmill runtime.
    """

    __slots__ = (
        'client'
    )

    def __init__(self, tm_env, container_dir):
        super(DockerRuntime, self).__init__(tm_env, container_dir)
        self.client = None

    def _can_run(self, manifest):
        try:
            return appcfg.AppType(manifest['type']) is appcfg.AppType.DOCKER
        except ValueError:
            return False

    def _get_client(self):
        """Gets the docker client.
        """
        if self.client is not None:
            return self.client

        self.client = docker.from_env()
        return self.client

    def _run(self, manifest):
        with lc.LogContext(_LOGGER, os.path.basename(self.container_dir),
                           lc.ContainerAdapter) as log:
            log.info('Running %r', self.container_dir)

            _sockets = runtime.allocate_network_ports(
                '0.0.0.0', manifest
            )

            app = runtime.save_app(manifest, self.container_dir)

            app_presence = presence.EndpointPresence(
                context.GLOBAL.zk.conn,
                manifest
            )

            app_presence.register()

            try:
                client = self._get_client()

                try:
                    container = _create_container(self.tm_env, client, app)
                except docker.errors.ImageNotFound:
                    raise exc.ContainerSetupError(
                        'Image {0} was not found'.format(app.image),
                        app_abort.AbortedReason.IMAGE
                    )

                container.start()
                container.reload()

                _LOGGER.info('Container is running.')
                appevents.post(
                    self.tm_env.app_events_dir,
                    events.ServiceRunningTraceEvent(
                        instanceid=app.name,
                        uniqueid=app.uniqueid,
                        service='docker'
                    )
                )

                while container.status == 'running':
                    container.wait(timeout=10)
                    container.reload()
            finally:
                _LOGGER.info('Stopping zookeeper.')
                context.GLOBAL.zk.conn.stop()

    def _finish(self):
        data_dir = os.path.join(self.container_dir, 'data')
        app = runtime.load_app(data_dir, runtime.STATE_JSON)

        if app:
            client = self._get_client()
            container = state = None
            name = appcfg.app_unique_name(app)
            try:
                container = client.containers.get(name)
                state = container.attrs.get('State')
            except docker.errors.NotFound:
                pass

            if container is not None:
                try:
                    container.remove(force=True)
                except docker.errors.APIError:
                    _LOGGER.error('Failed to remove %s', container.id)

            aborted = _check_aborted(data_dir)
            if aborted is not None:
                app_abort.report_aborted(self.tm_env, app.name,
                                         why=aborted.get('why'),
                                         payload=aborted.get('payload'))

            elif state is not None:
                if state.get('OOMKilled', False):
                    event = events.KilledTraceEvent(
                        instanceid=app.name,
                        is_oom=True,
                    )
                else:
                    event = events.FinishedTraceEvent(
                        instanceid=app.name,
                        rc=state.get('ExitCode', 256),
                        signal=0,
                        payload=state
                    )

                appevents.post(self.tm_env.app_events_dir, event)

            if os.name == 'nt':
                credential_spec.cleanup(name, client)

    def kill(self):
        client = self._get_client()
        name = os.path.basename(self.container_dir)
        try:
            container = client.containers.get(name)
            container.kill()
        except docker.errors.NotFound:
            pass