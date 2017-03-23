"""Reports presence information into Zookeeper."""


import errno
import os
import time
import logging
import subprocess
import sys

import kazoo
import yaml

from . import exc
from . import cgroups
from . import supervisor
from . import sysinfo
from . import utils
from . import subproc
from . import zkutils
from . import appevents

from . import logcontext as lc
from . import zknamespace as z

from .apptrace import events as traceevents


_LOGGER = lc.ContainerAdapter(logging.getLogger(__name__))

_SERVERS_ACL = zkutils.make_role_acl('servers', 'rwcd')

_INVALID_IDENTITY = sys.maxsize

# Max number of restart in a min, after which the app will not be restarted.
_MAX_RESTART_RATE = 5
_RESTART_RATE_INTERVAL = 60

# Time to wait when registering endpoints in case previous ephemeral
# endpoint is still present.
_EPHEMERAL_RETRY_INTERVAL = 5


def _create_ephemeral_with_retry(zkclient, path, data):
    """Create ephemeral node with retry."""
    prev_data = None
    for _ in range(0, 5):
        try:
            return zkutils.create(zkclient, path, data, acl=[_SERVERS_ACL],
                                  ephemeral=True)
        except kazoo.client.NodeExistsError:
            prev_data, metadata = zkutils.get_default(
                zkclient, path, need_metadata=True
            )
            _LOGGER.warn(
                'Node exists, will retry: %s, data: %r, metadata: %r',
                path, prev_data, metadata
            )
            time.sleep(_EPHEMERAL_RETRY_INTERVAL)

    raise exc.ContainerSetupError('presence.%s:%s' % (path, prev_data))


class EndpointPresence(object):
    """Manages application endpoint registration in Zookeeper."""

    def __init__(self, zkclient, manifest, hostname=None, appname=None):
        self.zkclient = zkclient
        self.manifest = manifest
        self.hostname = hostname if hostname else sysinfo.hostname()
        if appname:
            self.appname = appname
        else:
            self.appname = self.manifest.get('name')
        self.log = lc.Adapter(_LOGGER, self.appname)

    def register(self):
        """Register container in Zookeeper."""
        self.register_identity()
        self.register_running()
        self.register_endpoints()

    def register_running(self):
        """Register container as running."""
        self.log.logger.info('registering container as running: %s',
                             self.appname)
        _create_ephemeral_with_retry(self.zkclient,
                                     z.path.running(self.appname),
                                     self.hostname)

    def unregister_running(self):
        """Safely deletes the "running" node for the container."""
        self.log.logger.info('un-registering container as running: %s',
                             self.appname)
        path = z.path.running(self.appname)
        try:
            data, _metadata = self.zkclient.get(path)
            if data == self.hostname:
                self.zkclient.delete(path)
        except kazoo.client.NoNodeError:
            self.log.logger.info('running node does not exist.')

    def register_endpoints(self):
        """Registers service endpoint."""
        self.log.logger.info('registering endpoints: %s', self.appname)

        endpoints = self.manifest.get('endpoints', [])
        for endpoint in endpoints:
            internal_port = endpoint['port']
            ep_name = endpoint.get('name', str(internal_port))
            ep_port = endpoint['real_port']
            ep_proto = endpoint.get('proto', 'tcp')

            hostport = self.hostname + ':' + str(ep_port)
            path = z.path.endpoint(self.appname, ep_proto, ep_name)
            self.log.logger.info('register endpoint: %s %s', path, hostport)

            # Endpoint node is created with default acl. It is ephemeral
            # and not supposed to be modified by anyone.
            _create_ephemeral_with_retry(self.zkclient, path, hostport)

    def unregister_endpoints(self):
        """Unregisters service endpoint."""
        self.log.logger.info('registering endpoints: %s', self.appname)

        endpoints = self.manifest.get('endpoints', [])
        for endpoint in endpoints:
            port = endpoint.get('port', '')
            ep_name = endpoint.get('name', str(port))
            ep_proto = endpoint.get('proto', 'tcp')

            if not ep_name:
                self.log.critical('Logic error, no endpoint info: %s',
                                  self.manifest)
                return

            path = z.path.endpoint(self.appname, ep_proto, ep_name)
            self.log.logger.info('un-register endpoint: %s', path)
            try:
                data, _metadata = self.zkclient.get(path)
                if data.split(':')[0] == self.hostname:
                    self.zkclient.delete(path)
            except kazoo.client.NoNodeError:
                self.log.logger.info('endpoint node does not exist.')

    def register_identity(self):
        """Register app identity."""
        identity_group = self.manifest.get('identity_group')

        # If identity_group is not set or set to None, nothing to register.
        if not identity_group:
            return

        identity = self.manifest.get('identity', _INVALID_IDENTITY)

        self.log.logger.info('Register identity: %s, %s',
                             identity_group,
                             identity)
        _create_ephemeral_with_retry(
            self.zkclient,
            z.path.identity_group(identity_group, str(identity)),
            {'host': self.hostname, 'app': self.appname},
        )


def is_oom():
    """Checks memory failcount and return oom state of the container."""

    # NOTE(boysson): This code runs in the container's namespace so the memory
    #                cgroup is "masked".
    mem_failcnt = cgroups.makepath('memory', '/', 'memory.failcnt')
    memsw_failcnt = cgroups.makepath('memory', '/', 'memory.memsw.failcnt')

    try:
        with open(mem_failcnt) as f:
            mem_failcnt = int(f.read().strip())
        with open(memsw_failcnt) as f:
            memsw_failcnt = int(f.read().strip())
        return mem_failcnt != 0 or memsw_failcnt != 0
    except:  # pylint: disable=W0702
        _LOGGER.info('Cannot access memory failcnt.', exc_info=True)
        return False


def kill_node(zkclient, node):
    """Kills app, endpoints, and server node."""
    _LOGGER.info('killing node: %s', node)
    try:
        zkutils.get(zkclient, z.path.server(node))
    except kazoo.client.NoNodeError:
        _LOGGER.info('node does not exist.')
        return

    apps = zkclient.get_children(z.path.placement(node))
    for app in apps:
        _LOGGER.info('removing app presence: %s', app)
        try:
            manifest = zkutils.get(zkclient, z.path.scheduled(app))
            app_presence = EndpointPresence(zkclient,
                                            manifest,
                                            hostname=node,
                                            appname=app)
            app_presence.unregister_running()
            app_presence.unregister_endpoints()
        except kazoo.client.NoNodeError:
            _LOGGER.info('app %s no longer scheduled.', app)

    _LOGGER.info('removing node: %s', node)
    zkutils.ensure_deleted(zkclient, z.path.server_presence(node))


def is_down(svc_dir):
    """Check if service is running."""
    try:
        subproc.check_call(['s6-svwait', '-t', '100', '-d', svc_dir])
        return True
    except subprocess.CalledProcessError as err:
        # If wait timed out, the app is already running, do nothing.
        if err.returncode == 1:
            return False
        else:
            raise


class ServicePresence(object):
    """Manages service presence and lifecycle events."""

    def __init__(self, manifest, container_dir, appevents_dir,
                 hostname=None):
        self.manifest = manifest
        self.container_dir = container_dir
        self.services_dir = os.path.join(container_dir, 'services')
        self.appevents_dir = appevents_dir
        self.hostname = hostname if hostname else sysinfo.hostname()
        self.appname = self.manifest['name']
        self.uniqueid = self.manifest['uniqueid']
        self.services = self._services()
        self.log = lc.Adapter(_LOGGER, self.appname)

    def _services(self):
        """Constructs service by name dictionaty."""
        services = {}
        for service in self.manifest.get('services', []):
            services[service.get('name')] = service

        return services

    def ensure_supervisors_running(self):
        """Ensures that supervisor is started for each service."""
        for service in self.services:
            # Busy wait for service directory to become supervised.
            while not supervisor.is_supervisor_running(self.services_dir,
                                                       service):
                self.log.logger.info('%s/%s not yet supervised.',
                                     self.services_dir,
                                     service)
                time.sleep(0.5)

    def _actual_restarts(self, service_name, restart_data):
        """Returns the number of restarts for the given service."""
        actual_restarts = 0

        finished = os.path.join(self.services_dir, service_name, 'finished')

        restart_rate_exceeded = False
        try:
            with open(finished) as f:
                limit, interval = (
                    restart_data['limit'],
                    restart_data['interval']
                )
                lines = f.readlines()
                actual_restarts = len(lines)
                if limit == 0:
                    # Do not allow any restart
                    restart_rate_exceeded = True

                elif len(lines) >= limit:
                    # See if we went over the limit
                    timestamp, _rc, _sig = lines[-limit].split()
                    if int(timestamp) + interval > time.time():
                        restart_rate_exceeded = True

        except IOError as err:
            if err.errno != errno.ENOENT:
                raise

        return restart_rate_exceeded, actual_restarts

    def start_all(self):
        """Start all services."""
        for service_name in self.services:
            self.log.logger.info('Starting: %s', service_name)
            if not self.start_service(service_name):
                return False, service_name
        return True, None

    def start_service(self, service_name):
        """Instructs the supervisor to start the service if it is down."""
        # TODO(boysson): remove this. There is no reason why a manifest should
        #                lack restart_data.
        try:
            restart_data = self.services[service_name]['restart']
        except TypeError:
            self.log.error('Incorrect settings for restart')
            restart_data = {
                'limit': _MAX_RESTART_RATE,
                'interval': _RESTART_RATE_INTERVAL,
            }

        svc_dir = os.path.join(self.services_dir, service_name)

        restart_rate_exceeded, actual_restarts = (
            self._actual_restarts(service_name, restart_data))
        self.log.logger.info('starting %s, retries %s/%s in %s',
                             service_name, actual_restarts,
                             restart_data['limit'], restart_data['interval'])

        # If for whatever reason presence exited before reporting last exit
        # status, do it now. The method is no-op if last status was reported
        # successfully.
        self.update_exit_status(service_name)

        if restart_rate_exceeded:
            self.log.logger.info('Exceeded number of restarts per interval')
            return False

        if is_down(svc_dir):
            if os.path.exists(os.path.join(svc_dir, 'down')):
                subproc.check_call(['s6-svc', '-o', svc_dir])
            self.report_running(service_name)
        else:
            self.log.logger.info('Service %s already running', service_name)

        subproc.check_call(['s6-svwait', '-u', svc_dir])
        return True

    def wait_for_exit(self, container_svc_dir):
        """Waits for service to be down, reports status to zk."""
        watched_dirs = [os.path.join(self.services_dir, svc)
                        for svc in self.services]
        if container_svc_dir:
            watched_dirs.append(container_svc_dir)

        self.log.logger.info('waiting for service exit: %r', watched_dirs)

        # Wait for one of the services to come down.
        # TODO: need to investigate why s6-svwait returns 111 rather
        #                than 0.
        subproc.call(['s6-svwait', '-o', '-d'] + watched_dirs)

        # Wait for the supervisor to report finished status.
        time.sleep(1)

        for service in self.services:
            # If service is running, update_exit_status is noop.
            self.update_exit_status(service)

    def exit_info(self, svc_dir):
        """Constructs exit summary given service directory."""
        finished = os.path.join(svc_dir, 'finished')
        rc = -1
        signal = -1

        count = 0
        with open(finished) as f:
            lines = f.readlines()
            count = len(lines)
            last_line = lines[-1]
            timestamp, rc, signal = last_line.strip().split()

        log = os.path.join(svc_dir, 'log', 'current')
        logtail = ''.join(utils.tail(log))

        oom = is_oom()

        return {
            'hostname': self.hostname,
            'rc': int(rc),
            'sig': int(signal),
            'output': logtail,
            'oom': oom,
            'time': int(timestamp),
        }, count

    def update_exit_status(self, service_name):
        """Creates an entry under tasks/<host> object with the exit status."""
        svc_dir = os.path.join(self.services_dir, service_name)
        finished = os.path.join(svc_dir, 'finished')
        if not os.path.exists(finished):
            self.log.logger.info('%s/finished does not exist.', svc_dir)
            return

        task_id = self.manifest.get('task', None)
        if not task_id:
            self.log.error('Task id not found.')
            return

        exitinfo, count = self.exit_info(svc_dir)
        prev_count = None
        reported = os.path.join(svc_dir, 'reported')
        try:
            with open(reported) as f:
                prev_count = int(f.read())
        except IOError as err:
            if err.errno == errno.ENOENT:
                pass
            else:
                raise

        if prev_count == count:
            self.log.logger.info('Exit status already reported, count: %d',
                                 count)
            return

        self.log.logger.info('exit (rc, signal): (%s, %s)',
                             exitinfo['rc'], exitinfo['sig'])

        appevents.post(
            self.appevents_dir,
            traceevents.ServiceExitedTraceEvent(
                instanceid=self.appname,
                uniqueid=self.uniqueid,
                service=service_name,
                rc=exitinfo['rc'],
                signal=exitinfo['sig']
            )
        )

        # Records that exit status was successfully reported.
        with open(reported, 'w+') as f:
            f.write(str(count))

        self.services[service_name]['last_exit'] = exitinfo

    def report_running(self, service_name):
        """Creates ephemeral node indicating service has started."""
        self.log.logger.info('Service is running.')
        appevents.post(
            self.appevents_dir,
            traceevents.ServiceRunningTraceEvent(
                instanceid=self.appname,
                uniqueid=self.uniqueid,
                service=service_name
            )
        )

    def exit_app(self, service_name, killed=False):
        """Removes application from Zookeeper, trigger container shutdown."""
        self.log.logger.info('Exiting %s', self.appname)

        # Max restarts reached, kill the container.
        if service_name:
            last_exit = self.services[service_name].get('last_exit')
            if last_exit:
                last_exit['service'] = service_name
            else:
                last_exit = {'service': service_name}
        else:
            last_exit = {'service': None}

        last_exit.update({'killed': killed, 'oom': is_oom()})

        with open(os.path.join(self.container_dir, 'exitinfo'), 'w+') as f:
            f.write(yaml.dump(last_exit))
