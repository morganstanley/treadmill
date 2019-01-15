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
import sys
import socket
import time

import docker
import netifaces

from treadmill import appcfg
from treadmill import context
from treadmill import fs
from treadmill import exc
from treadmill import logcontext as lc
from treadmill import presence
from treadmill import runtime
from treadmill import trace
from treadmill import zkutils

from treadmill.appcfg import abort as app_abort
from treadmill.trace.app import events
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
        # real_port is not available at this time on Windows, docker will
        # randomly pick one for us, we will query it later
        if hasattr(endpoint, 'real_port'):
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
        time.sleep(1)

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


def _log_port_mapping_config(ports):
    if ports:
        port_str = ' '.join(
            ['{}:{}'.format(c_port, h_port)
             for c_port, h_port in ports.items()]
        )
    else:
        port_str = 'none'

    _LOGGER.info(
        'port mapping config (container port/proto : host port): %s', port_str)


def _create_container(tm_env, conf, client, app, volume_mapping):
    """Create docker container from given app.
    """
    ports = {}
    for endpoint in app.endpoints:
        port_key = '{0}/{1}'.format(endpoint.port, endpoint.proto)
        # let docker pick the host port for us, we will query it later
        ports[port_key] = None

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
        'network': conf.get('network', 'nat'),
        # 1024 is max number of shares for docker
        'cpu_shares': int(
            (app.cpu / (multiprocessing.cpu_count() * 100.0)) * 1024),
        'mem_limit': app.memory,
        'storage_opt': {
            'size': app.disk
        },
        'volumes': volume_mapping
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


def _device_ip(device):
    """Return the IPv4 address assigned to a give device.

    :param ``str``:
        Device name
    :returns:
        ``str`` - IPv4 address of the device
    """
    ifaddresses = netifaces.ifaddresses(device)
    # FIXME: We are making an assumption and always taking the first IPv4
    #        assigned to the device.
    return ifaddresses[netifaces.AF_INET][0]['addr']


def _update_network_info_in_manifest(container, manifest):
    """ update endpoint['real_port'] in manifest according to
        container setting
    """
    # wait until container is actually running  even when container.status is
    # 'running', container.attrs['State']['Running'] can be False,
    # and container.attrs['NetworkSettings']['Ports'] doesn't exist unitl
    # container.attrs['State']['Running'] is True
    container.reload()
    while container.status == 'running':
        if container.attrs['State']['Running']:
            # then query port mapping settings and update manifest
            mapping = container.attrs['NetworkSettings']['Ports']
            if mapping:
                for ep in manifest['endpoints']:
                    port_key = '{0}/{1}'.format(ep['port'], ep['proto'])
                    ep['real_port'] = mapping[port_key][0]['HostPort']

            _log_port_mapping_config(mapping)

            break

        time.sleep(1)
        container.reload()

    # update host ip
    manifest['network'] = {
        'external_ip': _device_ip(netifaces.interfaces()[0])
    }


def _create_docker_log_symlink(svc_data_dir):
    """ crete a app/data/service/log link which points to app/log/
        :param app_data_dir:
            app/data path
    """
    docker_data_dir = os.path.join(
        os.path.realpath(svc_data_dir),
        'services',
        'docker',
        'data'
    )

    fs.mkdir_safe(docker_data_dir)
    link = os.path.join(docker_data_dir, 'log')
    target = os.path.join(svc_data_dir, 'log')
    _LOGGER.info('linking %s -> %s', link, target)
    fs.symlink_safe(link, target)


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


def _print_container_logs(container):
    """Iterate and print container logs.
    """
    # with tty allocated, logs will be prefixed by some control
    # characters and it will make container.logs return char by char
    # instead of line by line so we need to fix it

    log_obj = container.logs(stream=True, follow=True)

    # skip first line of control characters
    for ch in log_obj:
        if ch.decode('utf-8') == '\n':
            break

    # print the rest of messages
    for ch in log_obj:
        print(ch.decode('utf-8'), file=sys.stdout, end='', flush=True)


class DockerRuntime(runtime_base.RuntimeBase):
    """Docker Treadmill runtime.
    """

    name = 'docker'

    __slots__ = (
        '_client',
        '_config'
    )

    def __init__(self, tm_env, container_dir, param=None):
        super(DockerRuntime, self).__init__(tm_env, container_dir, param)
        self._client = None
        self._config = None

    def _can_run(self, manifest):
        try:
            return appcfg.AppType(manifest['type']) is appcfg.AppType.DOCKER
        except ValueError:
            return False

    def _get_config(self):
        """Gets the docker client.
        """
        if self._config is not None:
            return self._config

        docker_conf = os.path.join(self._tm_env.configs_dir, 'docker.json')
        try:
            with io.open(docker_conf) as f:
                self._config = json.load(f)

        except IOError:
            _LOGGER.error('docker config file does not exist: %r', docker_conf)
            self._config = {}

        return self._config

    def _get_client(self):
        """Gets the docker client.
        """
        if self._client is not None:
            return self._client

        self._client = docker.from_env(**self._param)
        return self._client

    def _run(self, manifest):
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)

        with lc.LogContext(_LOGGER, self._service.name,
                           lc.ContainerAdapter) as log:
            log.info('Running %r', self._service.directory)

            manifest['ephemeral_ports']['tcp'] = []
            manifest['ephemeral_ports']['udp'] = []

            # create container_data dir
            container_data_dir = os.path.join(
                self._service.data_dir,
                'container_data'
            )

            log.info('container_data %r', container_data_dir)

            fs.mkdir_safe(container_data_dir)

            _create_docker_log_symlink(self._service.data_dir)

            # volume mapping config : read-only mapping
            volume_mapping = {
                container_data_dir: {
                    'bind': 'c:\\container_data',
                    'mode': 'ro'
                }
            }

            app = runtime.save_app(manifest, self._service.data_dir)

            app_presence = presence.EndpointPresence(
                context.GLOBAL.zk.conn,
                manifest
            )

            app_presence.register_identity()
            app_presence.register_running()

            client = self._get_client()

            try:
                container = _create_container(
                    self._tm_env,
                    self._get_config(),
                    client,
                    app,
                    volume_mapping
                )
            except docker.errors.ImageNotFound:
                raise exc.ContainerSetupError(
                    'Image {0} was not found'.format(app.image),
                    app_abort.AbortedReason.IMAGE
                )

            container.start()
            container.reload()

            _update_network_info_in_manifest(container, manifest)
            runtime.save_app(manifest, container_data_dir, app_json='app.json')

            _LOGGER.info('Container is running.')
            app_presence.register_endpoints()
            trace.post(
                self._tm_env.app_events_dir,
                events.ServiceRunningTraceEvent(
                    instanceid=app.name,
                    uniqueid=app.uniqueid,
                    service='docker'
                )
            )

            _print_container_logs(container)

    def _finish(self):
        app = runtime.load_app(self._service.data_dir, runtime.STATE_JSON)

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

            aborted = _check_aborted(self._service.data_dir)
            if aborted is not None:
                app_abort.report_aborted(self._tm_env, app.name,
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

                trace.post(self._tm_env.app_events_dir, event)

            if os.name == 'nt':
                credential_spec.cleanup(name, client)

            try:
                runtime.archive_logs(self._tm_env, name,
                                     self._service.data_dir)
            except Exception:  # pylint: disable=W0703
                _LOGGER.exception('Unexpected exception storing local logs.')

    def kill(self):
        app = runtime.load_app(self._service.data_dir, runtime.STATE_JSON)
        if not app:
            return

        name = appcfg.app_unique_name(app)
        try:
            client = self._get_client()
            container = client.containers.get(name)
            container.kill()
        except docker.errors.NotFound:
            pass
