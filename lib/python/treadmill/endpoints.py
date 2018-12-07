"""Functions for handling the network rules directory files.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import glob
import errno
import logging
import os
import time

from treadmill import fs
from treadmill import dirwatch
from treadmill import netutils
from treadmill import sysinfo
from treadmill import zknamespace as z
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)

# Keeping things portable, '~' is reasonable separator that works on Linux and
# Windows.
#
# Windows does not like neither (:) nor (,)
#
# TODO: consider encoding the file namb for safety?
_SEP = '~'

_GC_INTERVAL = 60


class EndpointsMgr:
    """Endpoints rule manager.

    Manages endpoints files for the host. The files are in the format:

    - appname:proto:endpoint:real_port:container_ip:port.

    """
    __slots__ = (
        '_base_path',
    )

    def __init__(self, base_path):
        # Make sure rules directory exists.
        fs.mkdir_safe(base_path)
        self._base_path = os.path.realpath(base_path)

    def initialize(self):
        """Initialize the network folder."""
        for spec in os.listdir(self._base_path):
            os.unlink(os.path.join(self._base_path, spec))

    @property
    def path(self):
        """Currently managed rules directory.

        :returns:
            ``str`` -- Spec directory.
        """
        return self._base_path

    def get_spec(self, proto=None, endpoint=None):
        """Get endpoint spec with partial pattern match.
        """
        pattern = (None, proto, endpoint, None, None, None)
        for spec in self.get_specs():
            if all(p is None or s == p for s, p in zip(spec, pattern)):
                return spec
        return None

    def get_specs(self):
        """Scrapes the spec directory for spec file.

        :returns:
            ``list`` -- List of endpoints specs.
        """
        specs = []

        for entry in os.listdir(self._base_path):
            if entry.startswith('.'):
                continue

            try:
                (appname,
                 proto,
                 endpoint,
                 real_port,
                 pid,
                 port) = entry.split(_SEP)
                specs.append((appname, proto, endpoint, real_port, pid, port))
            except ValueError:
                _LOGGER.warning('Incorrect endpoint format: %s', entry)

        return specs

    def create_spec(self, appname, proto, endpoint, real_port, pid,
                    port, owner):
        """Creates a symlink who's name represents the endpoint spec.
        """
        filename = _namify(
            appname=appname,
            proto=proto,
            endpoint=endpoint,
            real_port=real_port,
            pid=pid,
            port=port
        )
        rule_file = os.path.join(self._base_path, filename)

        # just create a regular file if no owner is supplied on Windows
        if owner is None:
            if not os.path.exists(rule_file):
                with open(rule_file, 'w'):
                    pass
                _LOGGER.info('File created %r for %r', filename, appname)
        else:
            try:
                os.symlink(
                    owner,
                    rule_file
                )
                _LOGGER.info('Symlink created %r for %r', filename, appname)
            except OSError as err:
                if err.errno == errno.EEXIST:
                    existing_owner = os.path.basename(os.readlink(rule_file))
                    if existing_owner != appname:
                        raise
                else:
                    raise

    def unlink_spec(self, appname, proto, endpoint, real_port, pid,
                    port, owner):
        """Unlinks the empty file who's name represents the endpoint spec.
        """
        filename = _namify(
            appname=appname,
            proto=proto,
            endpoint=endpoint,
            real_port=real_port,
            pid=pid,
            port=port
        )
        spec_file = os.path.join(self._base_path, filename)
        try:
            if owner:
                existing_owner = os.readlink(spec_file)
                if os.path.basename(existing_owner) != os.path.basename(owner):
                    _LOGGER.critical(
                        '%r tried to free %r that it does not own',
                        owner, filename)
                    return
            os.unlink(spec_file)
            _LOGGER.debug('Removed %r', filename)

        except OSError as err:
            if err.errno == errno.ENOENT:
                _LOGGER.info('endpoints spec %r does not exist.', spec_file)
            else:
                _LOGGER.exception('Unable to remove endpoint spec: %r',
                                  spec_file)
                raise

    def unlink_all(self, appname, proto=None, endpoint=None, owner=None):
        """Unlink all endpoints that match a given pattern."""
        if proto is None:
            proto = '*'
        if endpoint is None:
            endpoint = '*'
        filename = _namify(
            appname=appname,
            proto=proto,
            endpoint=endpoint,
            real_port='*',
            pid='*',
            port='*'
        )
        pattern = os.path.join(self._base_path, filename)
        _LOGGER.info('Unlink endpoints: %s, owner: %s', pattern, owner)
        for filename in glob.glob(pattern):
            try:
                if owner:
                    existing_owner = os.readlink(filename)
                    if os.path.basename(existing_owner) != owner:
                        _LOGGER.critical(
                            '%r tried to free %r that it does not own',
                            owner,
                            filename
                        )
                        continue

                _LOGGER.info('Remove stale endpoint spec: %s', filename)
                os.unlink(filename)
            except OSError as err:
                if err.errno == errno.ENOENT:
                    _LOGGER.info('endpoints spec %r does not exist.', filename)
                else:
                    _LOGGER.exception('Unable to remove endpoint spec: %s',
                                      filename)
                    raise


def _namify(appname, proto, endpoint, real_port, pid, port):
    """Create filename given all the parameters."""
    return _SEP.join([appname,
                      proto,
                      endpoint,
                      str(real_port),
                      str(pid),
                      str(port)])


class PortScanner:
    """Scan and publish local discovery and port status info."""

    def __init__(self, endpoints_dir, zkclient, scan_interval, instance=None):
        self.endpoints_dir = endpoints_dir
        self.zkclient = zkclient
        self.scan_interval = scan_interval
        self.hostname = sysinfo.hostname()
        self.state = collections.defaultdict(dict)
        self.node_acl = self.zkclient.make_host_acl(self.hostname, 'rwcd')
        self.instance = instance

    def _publish(self, result):
        """Publish network info to Zookeeper."""
        if self.instance:
            instance = '#'.join([self.hostname, self.instance])
        else:
            instance = self.hostname
        zkutils.put(
            self.zkclient,
            z.path.discovery_state(instance),
            result,
            ephemeral=True,
            acl=[self.node_acl]
        )

    def run(self, watchdog_lease=None):
        """Scan running directory in a watchdir loop."""

        garbage_collect(self.endpoints_dir)
        last_gc = time.time()
        prev_result = None

        while True:
            result = self._scan()
            if result != prev_result:
                self._publish(result)
                prev_result = result

            if watchdog_lease:
                watchdog_lease.heartbeat()

            if time.time() - last_gc > _GC_INTERVAL:
                garbage_collect(self.endpoints_dir)
                last_gc = time.time()

            time.sleep(self.scan_interval)

        _LOGGER.info('service shutdown.')
        if watchdog_lease:
            watchdog_lease.remove()

    def _scan(self):
        """Scan all container ports."""
        container_ports = collections.defaultdict(dict)
        container_pids = dict()
        for entry in os.listdir(self.endpoints_dir):
            if entry.startswith('.'):
                continue

            _LOGGER.debug('Entry: %s', entry)
            appname, endpoint, proto, real_port, pid, port = entry.split(_SEP)

            container_pids[appname] = pid

            port = int(port)
            real_port = int(real_port)
            container_ports[appname][port] = real_port

        real_port_status = dict()
        for appname, pid in container_pids.items():
            open_ports = netutils.netstat(pid)
            _LOGGER.debug(
                'Container %s listens on %r',
                appname, list(open_ports)
            )
            for port, real_port in container_ports[appname].items():
                if port in open_ports:
                    real_port_status[real_port] = 1
                else:
                    real_port_status[real_port] = 0

        return real_port_status


class EndpointPublisher:
    """Manages publishing endpoints to Zookeeper."""

    _MAX_REQUEST_PER_CYCLE = 10

    def __init__(self, endpoints_dir, zkclient, instance):
        self.endpoints_dir = endpoints_dir
        self.zkclient = zkclient
        self.up_to_date = True
        self.state = set()
        self.hostname = sysinfo.hostname()
        self.node_acl = self.zkclient.make_host_acl(self.hostname, 'rwcd')
        self.instance = instance

    def _on_created(self, path):
        """Add entry to the discovery set and mark set as not up to date."""
        if os.path.basename(path).startswith('.'):
            return

        entry = self._endpoint_info(path)
        _LOGGER.info('Added rule: %s', entry)
        self.state.add(entry)
        self.up_to_date = False

    def _on_deleted(self, path):
        """Add entry to the discovery set and mark set as not up to date."""
        entry = self._endpoint_info(path)
        _LOGGER.info('Removed rule: %s', entry)
        self.state.discard(entry)
        self.up_to_date = False

    def _publish(self):
        """Publish updated discovery info to Zookeeper."""
        _LOGGER.info('Publishing discovery info')
        state = list(sorted(self.state))
        if self.instance:
            instance = '#'.join([self.hostname, self.instance])
        else:
            instance = self.hostname
        zkutils.put(self.zkclient, z.path.discovery(instance),
                    state,
                    ephemeral=True, acl=[self.node_acl])

    def _endpoint_info(self, path):
        """Create endpoint info string from file path."""
        filename = os.path.basename(path)
        appname, endpoint, proto, port, _ = filename.split(_SEP, 4)
        return ':'.join([appname, endpoint, proto, port])

    def run(self):
        """Load and publish initial state."""
        watch_dir = self.endpoints_dir

        _LOGGER.info('Starting endpoint publisher: %s', watch_dir)

        watcher = dirwatch.DirWatcher(watch_dir)
        watcher.on_created = self._on_created
        watcher.on_deleted = self._on_deleted

        for fname in os.listdir(watch_dir):
            self._on_created(fname)

        self._publish()
        self.up_to_date = True

        while True:
            if watcher.wait_for_events(timeout=1):
                watcher.process_events(max_events=self._MAX_REQUEST_PER_CYCLE)

            if not self.up_to_date:
                self._publish()
                self.up_to_date = True


def garbage_collect(endpoints_dir):
    """Garbage collect all rules without owner.
    """
    for spec in os.listdir(endpoints_dir):
        link = os.path.join(endpoints_dir, spec)
        try:
            os.stat(link)

        except OSError as err:
            if err.errno == errno.ENOENT:
                _LOGGER.warning('Reclaimed: %r', spec)
                try:
                    os.unlink(link)
                except OSError as err:
                    if err.errno == errno.ENOENT:
                        pass
                    else:
                        raise
            else:
                raise
