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
import logging
import json
import os

import six

from treadmill import dirwatch
from treadmill import fs
from treadmill import plugin_manager
from treadmill import subproc
from treadmill import supervisor
from treadmill import utils

from treadmill.appcfg import abort as app_abort


_LOGGER = logging.getLogger(__name__)

_TOMESTONES_PLUGINS = 'treadmill.tombstones'
EXIT_INFO = 'exitinfo'


class Monitor:
    """Treadmill tombstone monitoring.

    Watches a directory for tombstone files and performs an action when it
    sees one.
    """

    __slots__ = (
        '_tm_env',
        '_config_dir',
        '_dispatcher',
        '_dirwatcher',
        '_tombstones'
    )

    def __init__(self, tm_env, config_dir):
        self._tm_env = tm_env
        self._config_dir = config_dir
        self._dirwatcher = None
        self._dispatcher = None
        self._tombstones = None

    def _on_created(self, path, handler):
        name = os.path.basename(path)
        if name[0] == '.':
            return

        tombstone_id, timestamp, rc, sig = name.rsplit(',', 3)

        tombstone = (path, handler, {
            'return_code': int(rc),
            'id': tombstone_id,
            'signal': int(sig),
            'timestamp': float(timestamp),
        })

        _LOGGER.info('Processing tombstone %r', tombstone)
        self._tombstones.append(tombstone)

    def _configure(self):
        """Configures the dispatcher with the monitor actions defined in
        the config directory.
        """
        config = {}

        for name in os.listdir(self._config_dir):
            path = os.path.join(self._config_dir, name)
            if not os.path.isfile(path):
                continue

            _LOGGER.debug('Configuring for file: %s', path)

            with io.open(path) as f:
                for line in f.readlines():
                    parts = line.rstrip().split(';', 2)
                    if len(parts) < 2:
                        _LOGGER.warning('skiping config line %s', line)
                        continue

                    try:
                        handler = plugin_manager.load(_TOMESTONES_PLUGINS,
                                                      parts[1])
                    except KeyError:
                        _LOGGER.warning('Tomestone handler does not exist: %r',
                                        parts[1])
                        continue

                    params = {}
                    if len(parts) > 2:
                        params = json.loads(parts[2])

                    impl = handler(self._tm_env, params)
                    config[parts[0]] = impl

        self._dirwatcher = dirwatch.DirWatcher()
        self._dispatcher = dirwatch.DirWatcherDispatcher(self._dirwatcher)
        self._tombstones = collections.deque()

        for path, handler in six.iteritems(config):
            fs.mkdir_safe(path)
            self._dirwatcher.add_dir(path)
            self._dispatcher.register(path, {
                dirwatch.DirWatcherEvent.CREATED:
                    lambda p, h=handler: self._on_created(p, h)
            })

            _LOGGER.info('Watching %s with handler %r', path, handler)

            for name in os.listdir(path):
                self._on_created(os.path.join(path, name), handler)

        _LOGGER.info('Monitor configured')

    def run(self):
        """Run the monitor.

        Start the event loop and process tombstone events as they are recieved.
        """
        self._configure()

        while True:
            while not self._tombstones:
                if self._dirwatcher.wait_for_events():
                    self._dirwatcher.process_events()

            # Process all the tombstones through the tombstone_action callback.
            for path, handler, data in self._tombstones:
                if handler.execute(data):
                    fs.rm_safe(path)

            # Clear the down reasons now that we have processed them all.
            self._tombstones.clear()


@six.add_metaclass(abc.ABCMeta)
class MonitorTombstoneAction:
    """Abstract base class for all monitor tombstone actions.

    Behavior when a service fails its policy.
    """
    __slots__ = (
        '_tm_env',
        '_params'
    )

    def __init__(self, tm_env, params=None):
        self._tm_env = tm_env

        if params is None:
            params = {}

        self._params = params

    @abc.abstractmethod
    def execute(self, data):
        """Execute the down action.

        :params ``dict`` data:
            Contains 'path', 'return_code', 'id', 'signal', 'timestamp'.

        :returns ``bool``:
            ``True`` - Monitor should delete the tombstone
        """


class MonitorNodeDown(MonitorTombstoneAction):
    """Monitor down action that disables the node by blacklisting it.

    Triggers the blacklist through the watchdog service.
    """
    __slots__ = ()

    def execute(self, data):
        """Shut down the node by writing a watchdog with the down reason data.
        """
        _LOGGER.critical('Node down: %r', data)
        filename = os.path.join(
            self._tm_env.watchdog_dir, 'Monitor-{prefix}{service}'.format(
                prefix=self._params.get('prefix', ''),
                service=data['id']
            )
        )
        fs.write_safe(
            filename,
            lambda f: f.write(
                'Node service {service!r} crashed.'
                ' Last exit {return_code} (sig:{signal}).'.format(
                    service=data['id'],
                    return_code=data['return_code'],
                    signal=data['signal']
                )
            ),
            prefix='.tmp',
            mode='w',
            permission=0o644
        )

        return False


class MonitorContainerCleanup(MonitorTombstoneAction):
    """Monitor container cleanup action.
    """
    __slots__ = ()

    def execute(self, data):
        """Pass a container to the cleanup service.
        """
        _LOGGER.critical('Monitor container cleanup: %r', data)
        running = os.path.join(self._tm_env.running_dir, data['id'])
        data_dir = supervisor.open_service(running, existing=False).data_dir
        cleanup = os.path.join(self._tm_env.cleanup_dir, data['id'])

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
            supervisor.control_svscan(self._tm_env.running_dir, [
                supervisor.SvscanControlAction.alarm,
                supervisor.SvscanControlAction.nuke
            ])
        except subproc.CalledProcessError as err:
            _LOGGER.warning('Failed to nuke svscan: %r',
                            self._tm_env.running_dir)

        return True


class MonitorContainerDown(MonitorTombstoneAction):
    """Monitor container down action.
    """
    __slots__ = ()

    def execute(self, data):
        """Put the container into the down state which will trigger cleanup.
        """
        _LOGGER.critical('Container down: %r', data)

        unique_name, service_name = data['id'].split(',')
        container_dir = os.path.join(self._tm_env.apps_dir, unique_name)
        container_svc = supervisor.open_service(container_dir)
        data_dir = container_svc.data_dir

        exitinfo_file = os.path.join(os.path.join(data_dir, EXIT_INFO))
        try:
            with io.open(exitinfo_file, 'x') as f:
                _LOGGER.info('Creating exitinfo file: %s', exitinfo_file)
                if os.name == 'posix':
                    os.fchmod(f.fileno(), 0o644)
                f.writelines(
                    utils.json_genencode({
                        'service': service_name,
                        'return_code': data['return_code'],
                        'signal': data['signal'],
                        'timestamp': data['timestamp']
                    })
                )
        except FileExistsError as err:
            _LOGGER.info('exitinfo file already exists: %s', exitinfo_file)

        try:
            supervisor.control_service(container_svc.directory,
                                       supervisor.ServiceControlAction.down)
        except subproc.CalledProcessError as err:
            _LOGGER.warning('Failed to bring down container: %s', unique_name)

        return True
