"""Monitor services.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import collections
import errno
import io
import json
import logging
import os

import enum
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import appevents
from treadmill import dirwatch
from treadmill import fs
from treadmill import supervisor
from treadmill import utils

from treadmill.appcfg import abort as app_abort
from treadmill.apptrace import events as traceevents


_LOGGER = logging.getLogger(__name__)

EXIT_INFO = 'exitinfo'


class Monitor(object):
    """Treadmill s6-based supervisor monitoring.

    Enforces restart policy and execute failure actions.
    """

    __slots__ = (
        '_dirwatcher',
        '_down_action',
        '_down_reasons',
        '_policy_impl',
        '_services',
        '_scan_dirs',
        '_service_policies',
        '_event_hook',
    )

    def __init__(self, scan_dirs, service_dirs, policy_impl, down_action,
                 event_hook=None):
        self._dirwatcher = None
        self._down_action = down_action
        self._down_reasons = collections.deque()
        self._event_hook = event_hook
        self._policy_impl = policy_impl
        self._services = list(utils.get_iterable(service_dirs))
        self._scan_dirs = set(utils.get_iterable(scan_dirs))
        self._service_policies = {}

    def _on_created(self, new_entry):
        if os.path.basename(new_entry)[0] == '.':
            return

        watched = os.path.dirname(new_entry)

        # Check if the created entry is a new service or a service exit entry
        if watched in self._scan_dirs:
            self._add_service(new_entry)

        else:
            # A service exited
            policy = self._service_policies.get(watched, None)
            if policy is not None:
                self._process(policy)

    def _on_deleted(self, removed_entry):
        if os.path.basename(removed_entry)[0] == '.':
            return

        _LOGGER.debug('Policies %r', self._service_policies)

        watched = os.path.dirname(removed_entry)
        if watched in self._scan_dirs:
            _LOGGER.debug('Removed scan dir')

        else:
            # If a policy directory is being removed, remove the associated
            # policy as well.
            removed_svc_policy = self._service_policies.pop(
                removed_entry, None
            )
            if removed_svc_policy is not None:
                _LOGGER.debug('Removed %r. Remaining policies %r',
                              removed_svc_policy, self._service_policies)
        return

    def _add_service(self, new_service_dir):
        # Add the new service
        try:
            service = supervisor.open_service(new_service_dir)

        except (ValueError, IOError):
            _LOGGER.exception('Unable to read service directory %r',
                              new_service_dir)
            return

        policy = self._policy_impl()
        new_watch = policy.register(service)

        if new_watch is None:
            _LOGGER.info('Service %r is not configured for monitoring',
                         service)
            return

        # Add the new service directory to the policy watcher
        try:
            self._dirwatcher.add_dir(new_watch)

        except OSError:
            _LOGGER.exception('Unable to add dir to watcher %r', new_watch)
            return

        self._service_policies[new_watch] = policy
        # Immediately ensure we start within policy.
        self._process(policy)

    def _process(self, policy):
        """Process an event on the service directory.
        """
        result = policy.check()

        if result is MonitorRestartPolicyResult.NOOP:
            return

        reason = policy.fail_reason
        self._went_down(policy.service, reason)

        if result is MonitorRestartPolicyResult.FAIL:
            self._down_reasons.append(reason)
            return

        else:
            self._bring_up(policy.service)
            self._went_up(policy.service)

    def _went_down(self, service, data):
        """Called when the service went down.

        :params ``supervisor.Service`` service:
            Service that went down.
        :params ``dict`` data:
            Policy reason data why the service went down.

        """
        _LOGGER.info('Service went down %r', service)
        if self._event_hook:
            self._event_hook.down(service, data)

    def _went_up(self, service):
        """Called when the service went up.

        :params ``supervisor.Service`` service:
            Service that went down.
        """
        _LOGGER.info('Service went up %r', service)
        if self._event_hook:
            self._event_hook.up(service)

    def _bring_up(self, service):
        """Brings up the given service.

        :params ``supervisor.Service`` service:
            Service to bring up.
        """
        _LOGGER.info('Bringing up service %r', service)
        try:
            # Check in one step the service is supervised and *not* up (we
            # expect it to be down).
            supervisor.wait_service(
                service.directory,
                supervisor.ServiceWaitAction.up,
                timeout=100
            )

            # Service is up, nothing to do.
            return

        except subprocess.CalledProcessError as err:
            if err.returncode == supervisor.ERR_NO_SUP:
                # Watching a directory without supervisor, nothing to do.
                return
            elif err.returncode == supervisor.ERR_TIMEOUT:
                # Service is down, make sure finish script is done.
                supervisor.wait_service(
                    service.directory,
                    supervisor.ServiceWaitAction.really_down,
                    timeout=(60 * 1000)
                )
            else:
                raise

        # Bring the service back up.
        supervisor.control_service(service.directory,
                                   supervisor.ServiceControlAction.up)

    def run(self):
        """Run the monitor.

        Start the event loop and continue until a service fails and the
        configure down action considers it fatal.
        """
        self._dirwatcher = dirwatch.DirWatcher()
        self._dirwatcher.on_deleted = self._on_deleted
        self._dirwatcher.on_created = self._on_created

        service_dirs = self._services[:]

        for scan_dir in self._scan_dirs:
            # If we have a svscan directory to watch add it.
            self._dirwatcher.add_dir(scan_dir)
            service_dirs += [
                os.path.join(scan_dir, dentry)
                for dentry in os.listdir(scan_dir)
                if dentry[0] != '.'
            ]

        for service_dir in service_dirs:
            self._add_service(service_dir)

        running = True
        while running:
            while not self._down_reasons:
                if self._dirwatcher.wait_for_events():
                    self._dirwatcher.process_events()

            # Process all the down reasons through the down_action callback.
            for down_reason in self._down_reasons:
                if not self._down_action.execute(down_reason):
                    # If one of the down_action stops the monitor, break early.
                    running = False
                    break
            else:
                # Clear the down reasons now that we have processed them all.
                self._down_reasons.clear()


@six.add_metaclass(abc.ABCMeta)
class MonitorDownAction(object):
    """Abstract base class for all monitor down actions.

    Behavior when a service fails its policy.
    """
    __slots__ = ()

    @abc.abstractmethod
    def execute(self, data):
        """Execute the down action.

        :params ``dict`` data:
            Output of the `class:MonitorPolicy.fail_reason()` method.

        :returns ``bool``:
            ``True`` - Monitor should keep running.
            ``False`` - Monitor should stop.
        """
        pass


class MonitorNodeDown(MonitorDownAction):
    """Monitor down action that disables the node by blacklisting it.

    Triggers the blacklist through the watchdog service.
    """
    __slots__ = (
        '_watchdog_dir',
        '_prefix'
    )

    def __init__(self, tm_env, prefix=''):
        self._watchdog_dir = tm_env.watchdog_dir
        self._prefix = prefix

    def execute(self, data):
        """Shut down the node by writing a watchdog with the down reason data.
        """
        _LOGGER.critical('Node down: %r', data)
        filename = os.path.join(
            self._watchdog_dir, 'Monitor-{prefix}{service}'.format(
                prefix=self._prefix,
                service=data['service']
            )
        )
        fs.write_safe(
            filename,
            lambda f: f.write(
                'Node service {service!r} crashed.'
                ' Last exit {return_code} (sig:{signal}).'.format(
                    service=data['service'],
                    return_code=data['return_code'],
                    signal=data['signal']
                )
            ),
            prefix='.tmp',
            mode='w',
            permission=0o644
        )

        return True


class MonitorContainerCleanup(MonitorDownAction):
    """Monitor container cleanup action.
    """
    __slots__ = (
        '_running_dir',
        '_cleanup_dir'
    )

    def __init__(self, tm_env):
        self._running_dir = tm_env.running_dir
        self._cleanup_dir = tm_env.cleanup_dir

    def execute(self, data):
        """Pass a container to the cleanup service.
        """
        _LOGGER.critical('Monitor container cleanup: %r', data)
        running = os.path.join(self._running_dir, data['service'])
        data_dir = supervisor.open_service(running).data_dir
        cleanup = os.path.join(self._cleanup_dir, data['service'])

        # pid1 will SIGABRT(6) when there is an issue
        if int(data['signal']) == 6:
            app_abort.flag_aborted(data_dir, why=app_abort.AbortedReason.PID1)

        try:
            _LOGGER.info('Moving %r -> %r', running, cleanup)
            fs.replace(running, cleanup)
        except OSError as err:
            if err.errno == errno.ENOENT:
                pass
            else:
                raise

        try:
            supervisor.control_svscan(self._running_dir, [
                supervisor.SvscanControlAction.alarm,
                supervisor.SvscanControlAction.nuke
            ])
        except subprocess.CalledProcessError as err:
            _LOGGER.warning('Failed to nuke svscan: %r', self._running_dir)

        return True


class MonitorContainerDown(MonitorDownAction):
    """Monitor container down action.
    """
    __slots__ = (
        '_container_svc',
    )

    def __init__(self, container_dir):
        self._container_svc = supervisor.open_service(container_dir)

    def execute(self, data):
        """Execute the down action.

        :returns ``bool``:
            ``True`` - Monitor should keep running.
            ``False`` - Monitor should stop.
        """
        _LOGGER.critical('Container down: %r', data)
        data_dir = self._container_svc.data_dir
        fs.write_safe(
            os.path.join(data_dir, EXIT_INFO),
            lambda f: f.writelines(
                utils.json_genencode(data)
            ),
            mode='w',
            prefix='.tmp',
            permission=0o644
        )
        # NOTE: This will take down this container's monitor service as well.
        # NOTE: The supervisor has to be running as we call from inside the
        #       container.
        supervisor.control_service(self._container_svc.directory,
                                   supervisor.ServiceControlAction.down)

        return False


@six.add_metaclass(abc.ABCMeta)
class MonitorEventHook(object):
    """Abstract base class for monitor events.
    """
    __slots__ = ()

    @abc.abstractmethod
    def down(self, service, data):
        """Called when a service has went down.

        :params service:
            The service that went down.
        :params ``dict`` data:
            Output of the `class:MonitorPolicy.fail_reason()` method.
        """
        pass

    # pylint complains: Invalid class attribute name "up"
    @abc.abstractmethod
    def up(self, service):  # pylint: disable=C0103
        """Called when a service has been brought back up.

        :params service:
            The service that has been brought back up.
        """
        pass


class PresenceMonitorEventHook(MonitorEventHook):
    """Adds hooks to the monitor to enable presence."""
    __slots__ = (
        'tm_env',
    )

    def __init__(self, tm_env):
        self.tm_env = tm_env

    def _get_trace(self, service):
        """Gets the trace details for the given service."""
        trace_file = os.path.join(service.data_dir, supervisor.TRACE_FILE)

        if not os.path.exists(trace_file):
            return None

        with io.open(trace_file) as f:
            return json.load(f)

    def down(self, service, data):
        trace = self._get_trace(service)
        if trace is None:
            return

        appevents.post(
            self.tm_env.app_events_dir,
            traceevents.ServiceExitedTraceEvent(
                instanceid=trace['instanceid'],
                uniqueid=trace['uniqueid'],
                service=service.name,
                rc=data['return_code'],
                signal=data['signal']
            )
        )

    def up(self, service):
        trace = self._get_trace(service)
        if trace is None:
            return

        appevents.post(
            self.tm_env.app_events_dir,
            traceevents.ServiceRunningTraceEvent(
                instanceid=trace['instanceid'],
                uniqueid=trace['uniqueid'],
                service=service.name
            )
        )


@six.add_metaclass(abc.ABCMeta)
class MonitorPolicy(object):
    """Abstract base class of all monitor policies implementations.

    Behaviors for policing services executions.
    """
    __slots__ = ()

    @abc.abstractmethod
    def register(self, service):
        """Register a service directory with the Monitor.

        :returns:
            ``str`` -- Absolute (real) path to the watch that needs to be added
                       to the monitor.
            ``None`` -- Policy registration failed. No watch will be created.
        """
        pass

    @abc.abstractproperty
    def check(self):
        """Check the status of the service against the policy.

        :returns ``MonitorRestartPolicyResult``:
            ``NOOP`` is nothing needs be done, ``RESTART`` to bring the service
             back up and ``FAIL`` to fail.
        """
        return

    @abc.abstractproperty
    def service(self):
        """The service which this policy is for

        :returns:
            The service.
        """
        return

    @abc.abstractproperty
    def fail_reason(self):
        """Policy failure data

        :returns ``dict``:
            Dictionary of failure data.
        """
        return


class MonitorRestartPolicyResult(enum.Enum):
    """Results of a MonitorRestartPolicy check.
    """
    NOOP = 'noop'
    RESTART = 'restart'
    FAIL = 'fail'


class MonitorRestartPolicy(MonitorPolicy):
    """Restart services based on limit and interval.
    """

    __slots__ = (
        '_last_rc',
        '_last_signal',
        '_last_timestamp',
        '_policy_interval',
        '_policy_limit',
        '_service',
        '_service_exits_log',
    )

    def __init__(self):
        self._last_rc = None
        self._last_signal = None
        self._last_timestamp = None
        self._policy_interval = None
        self._policy_limit = None
        self._service = None
        self._service_exits_log = None

    def register(self, service):
        self._service = service
        try:
            with io.open(os.path.join(service.data_dir,
                                      supervisor.POLICY_JSON)) as f:
                policy_conf = json.load(f)
            self._policy_limit = policy_conf['limit']
            self._policy_interval = policy_conf['interval']

        except IOError as err:
            if err.errno == errno.ENOENT:
                _LOGGER.warning('No policy file found for %r', service)
                return None
            else:
                raise

        service_exits_log = os.path.join(
            service.data_dir, supervisor.EXITS_DIR
        )
        fs.mkdir_safe(service_exits_log)
        self._service_exits_log = service_exits_log

        _LOGGER.info('monitoring %r with limit:%d interval:%d',
                     self._service, self._policy_limit, self._policy_interval)

        return os.path.realpath(service_exits_log)

    def check(self):
        try:
            exits = sorted([
                direntry
                for direntry in os.listdir(self._service_exits_log)
                if direntry[0] != '.'
            ])
        except OSError:
            _LOGGER.info('Dir %r was deleted.', self._service_exits_log)
            # The dir deleted event will remove from watcher
            return MonitorRestartPolicyResult.NOOP

        total_restarts = len(exits)
        if total_restarts == 0:
            # If it never exited, nothing to do
            return MonitorRestartPolicyResult.NOOP

        last_timestamp, last_rc, last_sig = exits[-1].split(',')
        self._last_timestamp = float(last_timestamp)
        self._last_rc = int(last_rc)
        self._last_signal = int(last_sig)

        success = True
        if total_restarts > self._policy_limit:
            if self._policy_limit == 0:
                # Do not allow any restart
                success = False

            else:
                # Check if within policy
                cutoff_exit = exits[-(self._policy_limit + 1)]
                timestamp, _rc, _sig = cutoff_exit.split(',')
                if (float(timestamp) + self._policy_interval >
                        self._last_timestamp):
                    success = False

        if not success:
            _LOGGER.critical(
                '%r restart rate exceeded. Last exit @%r code %r (sig:%r)',
                self._service,
                self._last_timestamp, self._last_rc, self._last_signal
            )
            return MonitorRestartPolicyResult.FAIL

        else:
            # Otherwise, restart the service
            _LOGGER.info(
                '%r should be up. Last exit @%r code %r (sig:%r)',
                self._service,
                self._last_timestamp, self._last_rc, self._last_signal
            )
            # Cleanup old exits (up to 2x the policy)
            for old_exit in exits[:-(self._policy_limit * 2)]:
                os.unlink(os.path.join(self._service_exits_log, old_exit))

            return MonitorRestartPolicyResult.RESTART

    @property
    def service(self):
        return self._service

    @property
    def fail_reason(self):
        return {
            'return_code': self._last_rc,
            'service': self._service.name,
            'signal': self._last_signal,
            'timestamp': self._last_timestamp,
        }


class CleanupMonitorRestartPolicy(MonitorRestartPolicy):
    """Restart services based on limit and interval only when cleanup
    is still to be done.
    """

    __slots__ = (
        '_tm_env'
    )

    def __init__(self, tm_env):
        super(CleanupMonitorRestartPolicy, self).__init__()
        self._tm_env = tm_env

    def check(self):
        name = os.path.basename(self._service.directory)
        cleanup_link = os.path.join(self._tm_env.cleanup_dir, name)
        if os.path.islink(cleanup_link):
            return super(CleanupMonitorRestartPolicy, self).check()
        else:
            # Cleanup link removed so cleanup has done its job
            return MonitorRestartPolicyResult.NOOP
