"""Supervises services."""

import abc
import errno
import logging
import os
import tempfile

import enum
import yaml

from treadmill import fs
from treadmill import dirwatch
from treadmill import subproc
from treadmill import supervisor


_LOGGER = logging.getLogger(__name__)


class Monitor(object):
    """Treadmill s6-based supervisor monitoring.

    Enforces restart policy and execute failure actions.
    """

    __slots__ = (
        '_dirwatcher',
        '_down_action',
        '_down_reason',
        '_policy_impl',
        '_services',
        '_services_dir',
        '_service_policies',
    )

    def __init__(self, services_dir, service_dirs, policy_impl, down_action):
        self._dirwatcher = None
        self._down_action = down_action
        self._down_reason = None
        self._policy_impl = policy_impl
        self._services = list(service_dirs)
        self._services_dir = services_dir
        self._service_policies = {}

    def _on_created(self, new_entry):
        if os.path.basename(new_entry)[0] == '.':
            return

        watched = os.path.dirname(new_entry)

        # Check if the created entry is a new service or a service exit entry
        if watched == self._services_dir:
            self._add_service(new_entry)

        else:
            # A service exited
            policy = self._service_policies.get(watched, None)
            if policy is None:
                return

            if not policy.process():
                self._down_reason = policy.fail_reason

    def _on_deleted(self, removed_entry):
        if os.path.basename(removed_entry)[0] == '.':
            return

        _LOGGER.debug('Policies %r', self._service_policies)

        watched = os.path.dirname(removed_entry)
        if watched == self._services_dir:
            _LOGGER.debug('Removed service dir')

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
        self._service_policies[new_watch] = policy
        # Add the new service directory to the policy watcher
        self._dirwatcher.add_dir(new_watch)
        # Immediately ensure we start within policy.
        if not policy.process():
            self._down_reason = policy.fail_reason

    def run(self):
        """Run the monitor.

        Start the event loop and continue until a service fails and the
        configure down action considers it fatal.
        """
        self._dirwatcher = dirwatch.DirWatcher()
        self._dirwatcher.on_deleted = self._on_deleted
        self._dirwatcher.on_created = self._on_created

        service_dirs = self._services[:]

        if self._services_dir is not None:
            # If we have a svscan directory to watch add it.
            self._dirwatcher.add_dir(self._services_dir)
            service_dirs += [
                os.path.join(self._services_dir, dentry)
                for dentry in os.listdir(self._services_dir)
                if dentry[0] != '.'
            ]

        for service_dir in service_dirs:
            self._add_service(service_dir)

        keep_running = True
        while keep_running:
            while self._down_reason is None:
                if self._dirwatcher.wait_for_events():
                    self._dirwatcher.process_events()

            keep_running = self._down_action.execute(self._down_reason)
            self._down_reason = None

        return


class MonitorDownAction(object):
    """Abstract base clase for all monitor down actions.

    Behavior when a service fails its policy.
    """
    __metaclass__ = abc.ABCMeta
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
        '_watchdog_dir'
    )

    def __init__(self, tm_env):
        self._watchdog_dir = tm_env.watchdog_dir

    def execute(self, data):
        """Shut down the node by writing a watchdog with the down reason data.
        """
        _LOGGER.critical('Node down: %r', data)
        with tempfile.NamedTemporaryFile(prefix='.tmp',
                                         dir=self._watchdog_dir,
                                         delete=False,
                                         mode='w') as f:
            f.write(
                'Node service {service!r} crashed.'
                ' Last exit {return_code} (sig:{signal}).'.format(
                    service=data['service'],
                    return_code=data['return_code'],
                    signal=data['signal']
                )
            )
            os.fchmod(f.fileno(), 0o644)
        os.rename(
            f.name,
            os.path.join(self._watchdog_dir, 'Monitor-%s' % data['service'])
        )

        return True


class MonitorPolicy(object):
    """Abstract base class of all monitor policies implementations.

    Behaviors for policing services executions.
    """
    __metaclass__ = abc.ABCMeta
    __slots__ = ()

    @abc.abstractmethod
    def register(self, service):
        """Register a service directory with the Monitor.

        :returns ``str``:
            Absolute (real) path to the watch that needs to be added to the
            monitor.
        """
        pass

    @abc.abstractmethod
    def process(self):
        """Process an service event.

        Ensure the service is down, check the policy and decide to restart the
        service or not.

        :returns ``bool``:
            True - Service still in compliance.
            False - Server failed policy.
        """
        pass

    @abc.abstractproperty
    def fail_reason(self):
        """Policy failure data

        :returns ``dict``:
            Dictionary of failure data
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

    EXITS_DIR = 'exits'
    POLICY_FILE = 'policy.yml'
    # TODO(boysson): configurable timeout for really down
    REALLY_DOWN_TIMEOUT = '50'

    def __init__(self):
        self._last_rc = None
        self._last_signal = None
        self._last_timestamp = None
        self._policy_interval = None
        self._policy_limit = None
        self._service = None
        self._service_exits_log = None

    @property
    def fail_reason(self):
        return {
            'return_code': self._last_rc,
            'service': self._service.name,
            'signal': self._last_signal,
            'timestamp': self._last_timestamp,
        }

    def register(self, service):
        self._service = service
        try:
            with open(os.path.join(service.data_dir, self.POLICY_FILE)) as f:
                policy_conf = yaml.load(stream=f)
                self._policy_limit = policy_conf['limit']
                self._policy_interval = policy_conf['interval']

        except IOError as err:
            if err.errno == errno.ENOENT:
                self._policy_limit = 0
                self._policy_interval = 60
            else:
                raise

        service_exits_log = os.path.join(
            service.data_dir, self.EXITS_DIR
        )
        fs.mkdir_safe(service_exits_log)
        self._service_exits_log = service_exits_log

        _LOGGER.info('monitoring %r with limit:%d interval:%d',
                     self._service, self._policy_limit, self._policy_interval)

        return os.path.realpath(service_exits_log)

    def process(self):
        """Process an event on the service directory
        """
        result = self._check_policy()
        if result is MonitorRestartPolicyResult.NOOP:
            return True

        elif result is MonitorRestartPolicyResult.FAIL:
            return False

        else:
            # Bring the service back up.
            _LOGGER.info('Bringing up %r', self._service)
            subproc.check_call(
                [
                    's6_svc', '-u',
                    self._service.directory
                ]
            )

        return True

    def _check_policy(self):
        """Check the status of the service against the policy.

        :returns ``MonitorRestartPolicyResult``:
            ``NOOP`` is nothing needs be done, ``RESTART`` to bring the service
             back up and ``FAIL`` to fail.
        """
        exits = sorted([
            direntry
            for direntry in os.listdir(self._service_exits_log)
            if direntry[0] != '.'
        ])

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
