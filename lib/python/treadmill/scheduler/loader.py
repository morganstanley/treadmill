"""Treadmill master process.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import fnmatch
import logging
import re
import time

from treadmill import admin
from treadmill import presence
from treadmill import reports
from treadmill import scheduler
from treadmill import utils
from treadmill import zknamespace as z

from . import backend as be


_LOGGER = logging.getLogger(__name__)


def _alloc_key(name):
    """Constructs allocation key based on app name/pattern."""
    if '@' in name:
        key = name[name.find('@') + 1:name.find('.')]
    else:
        key = name[0:name.find('.')]
    return key


def resources(data):
    """Convert resource demand/capacity spec into resource vector."""
    parsers = {
        'memory': utils.megabytes,
        'disk': utils.megabytes,
        'cpu': utils.cpu_units
    }

    return [parsers[k](data.get(k, 0)) for k in ['memory', 'cpu', 'disk']]


def _get_data_retention(data):
    """Returns data retention timeout in seconds."""
    data_retention_timeout = data.get('data_retention_timeout')
    if data_retention_timeout is not None:
        return utils.to_seconds(data_retention_timeout)
    else:
        return None


def _get_lease(data):
    """Returns lease attribute converted to seconds."""
    return utils.to_seconds(data.get('lease', '0s'))


class Loader(object):
    """Cell scheduler loader."""
    __slots__ = (
        'backend',
        'cell',
        'buckets',
        'servers',
        'allocations',
        'assignments',
        'partitions',
    )

    def __init__(self, backend, cellname):
        self.backend = backend
        self.cell = scheduler.Cell(cellname)
        self.buckets = dict()
        self.servers = dict()
        self.allocations = dict()
        self.assignments = collections.defaultdict(list)
        self.partitions = dict()

    def load_model(self):
        """Load cell state from Zookeeper."""
        self.load_partitions()
        self.load_buckets()
        self.load_cell()
        self.load_servers()
        self.load_allocations()
        self.load_strategies()
        self.load_apps()
        self.load_identity_groups()
        self.restore_placements()

    def load_cell(self):
        """Construct cell from top level buckets."""
        buckets = self.backend.list(z.CELL)
        self.cell.reset_children()
        for bucketname in buckets:
            _LOGGER.info('adding bucket to cell: %s', bucketname)
            self.cell.add_node(self.buckets[bucketname])

    def load_partitions(self):
        """Load partitions."""
        # Create default partition.
        self.cell.partitions[admin.DEFAULT_PARTITION] = scheduler.Partition(
            label=admin.DEFAULT_PARTITION
        )

        partitions = self.backend.list(z.PARTITIONS)
        for partition in partitions:
            self.load_partition(partition)

    def load_partition(self, partition):
        """Load partition."""
        try:
            _LOGGER.info('loading partition: %s', partition)
            data = self.backend.get(z.path.partition(partition))

            self.cell.partitions[partition] = scheduler.Partition(
                reboot_days=data.get('reboot-schedule'),
                label=partition
            )

        except be.ObjectNotFoundError:
            _LOGGER.warning('Partition node not found: %s', partition)

    def load_buckets(self):
        """Load bucket hierarchy."""
        buckets = self.backend.list(z.BUCKETS)
        for bucketname in buckets:
            self.load_bucket(bucketname)

    def load_bucket(self, bucketname):
        """Load bucket info, assume parent is already created."""
        # Do not load twice.
        if bucketname in self.buckets:
            return self.buckets[bucketname]

        _LOGGER.info('loading bucket: %s', bucketname)
        data = self.backend.get_default(z.path.bucket(bucketname),
                                        default={})
        traits = data.get('traits', 0)

        level = data.get('level', bucketname.split(':')[0])
        bucket = scheduler.Bucket(bucketname, traits=traits, level=level)
        self.buckets[bucketname] = bucket

        parent_name = data.get('parent')
        if parent_name:
            parent = self.load_bucket(parent_name)
            parent.add_node(bucket)
        return bucket

    def load_servers(self):
        """Load server topology."""
        servers = self.backend.list(z.SERVERS)
        for servername in servers:
            self.load_server(servername)

    def create_server(self, servername, data):
        """Create a new server object from server data."""
        label = data.get('partition')
        if not label:
            # TODO: it will be better to have separate module for constants
            #       and avoid unnecessary cross imports.
            label = admin.DEFAULT_PARTITION
        up_since = data.get('up_since', int(time.time()))

        server = scheduler.Server(
            servername,
            resources(data),
            up_since=up_since,
            label=label,
            traits=data.get('traits', 0)
        )
        return server

    def load_server(self, servername):
        """Load individual server."""
        _LOGGER.info('Loading server: %s', servername)

        try:
            data = self.backend.get(z.path.server(servername))
            if not data:
                # The server is configured, but never reported it's capacity.
                _LOGGER.info('No capacity detected: %s',
                             z.path.server(servername))
                return

            server = self.create_server(servername, data)

            # Add server to appropriate parent bucket.
            assert 'parent' in data
            parentname = data['parent']
            parent = self.buckets.get(parentname)
            if not parent:
                _LOGGER.warning('Server parent does not exist: %s/%s',
                                servername, parentname)
                return

            self.buckets[parentname].add_node(server)
            assert server.parent == self.buckets[parentname]

            self.set_server_presence(server)
            self.servers[servername] = server
            self.backend.ensure_exists(z.path.placement(servername))

        except be.ObjectNotFoundError:
            _LOGGER.warning('Server node not found: %s', servername)

    def remove_server(self, servername):
        """Remove server from scheduler."""
        if servername not in self.servers:
            return

        server = self.servers[servername]
        server.remove_all()
        server.parent.remove_node(server)

        for label in server.labels:
            self.cell.partitions[label].remove(server)

        del self.servers[servername]

    def reload_servers(self, servers):
        """Reload servers in the list."""
        for server in servers:
            self.reload_server(server)

    def reload_server(self, servername):
        """Reload individual server."""
        _LOGGER.info('Reloading server: %s', servername)

        if servername not in self.servers:
            # This server was never loaded.
            self.load_server(servername)
            return

        current_server = self.servers[servername]

        # Check if server is same
        try:
            data = self.backend.get(z.path.server(servername))
            if not data:
                # The server is configured, but never reported it's capacity.
                _LOGGER.info('No capacity detected: %s, removing server.',
                             z.path.server(servername))
                self.remove_server(servername)
                return

            server = self.create_server(servername, data)

            # TODO: need better error handling.
            assert 'parent' in data
            assert data['parent'] in self.buckets

            parent = self.buckets[data['parent']]
            # TODO: assume that bucket topology is constant, e.g.
            #                rack can never change buiding. If this does not
            #                hold, comparing parents is not enough, need to
            #                compare recursively all the way up.
            if (current_server.is_same(server) and
                    current_server.parent == parent):
                # Nothing changed, no need to update anything.
                _LOGGER.info('server is same, keeping old.')
                current_server.up_since = server.up_since
            else:
                # Something changed, replace server (remove and load as new).
                _LOGGER.info('server modified, replacing.')
                self.remove_server(servername)
                self.load_server(servername)

        except be.ObjectNotFoundError:
            self.remove_server(servername)
            _LOGGER.warning('Server node not found: %s', servername)

    def set_server_presence(self, server):
        """Set server presence, update state and valid_until accordingly."""
        server.presence_id = None
        for node in sorted(self.backend.list(z.SERVER_PRESENCE), reverse=True):
            servername, presence_id = presence.parse_server(node)
            if server.name == servername:
                server.presence_id = presence_id
                break

        if server.presence_id:
            _LOGGER.info('Server is up: %s (presence id: %s)',
                         server.name, server.presence_id)
        else:
            _LOGGER.info('Server is down: %s', server.name)

        self.adjust_server_state(server)
        self.adjust_server_valid_until(server)

    def adjust_server_state(self, server):
        """Set server state."""
        is_up = bool(server.presence_id)

        placement_node = z.path.placement(server.name)

        # Restore state as it was stored in server placement node.
        state_since = self.backend.get_default(placement_node)
        if not state_since:
            state_since = {'state': 'down', 'since': time.time()}

        state = scheduler.State(state_since['state'])
        since = state_since['since']
        server.set_state(state, since)

        # If presence does not exist - adjust state to down.
        if not is_up:
            server.state = scheduler.State.down
        else:
            if server.state is not scheduler.State.frozen:
                server.state = scheduler.State.up

        # Record server state:
        state, since = server.get_state()
        self.backend.put(
            placement_node, {'state': state.value, 'since': since})

    def adjust_server_valid_until(self, server):
        """Set server valid_until."""
        if not server.presence_id:
            if server.valid_until:
                # Remove server from reboot buckets and reset valid_until to 0.
                for label in server.labels:
                    self.cell.partitions[label].remove(server)
                server.valid_until = 0
            return

        server_presence_path = z.path.server_presence(
            presence.server_node(server.name, server.presence_id)
        )

        try:
            data = self.backend.get(server_presence_path)
            if not data:
                data = {}

            valid_until = data.get('valid_until')

            for label in server.labels:
                self.cell.partitions[label].add(server, valid_until)

            data = {'valid_until': server.valid_until}
            self.backend.update(server_presence_path, data, check_content=True)
        except be.ObjectNotFoundError:
            # Server presence changed, it will be adjusted.
            pass

    def load_allocations(self):
        """Load allocations and assignments map."""
        data = self.backend.get_default(z.ALLOCATIONS, default={})
        if not data:
            return

        self.assignments = collections.defaultdict(list)
        for obj in data:
            partition = obj.get('partition')
            name = obj['name']

            _LOGGER.info('Loading allocation: %s into partition: %s',
                         name, partition)

            alloc = self.cell.partitions[partition].allocation
            for part in re.split('[/:]', name):
                alloc = alloc.get_sub_alloc(part)

            capacity = resources(obj)
            alloc.update(capacity, obj['rank'], obj.get('rank_adjustment'),
                         obj.get('max_utilization'))

            for assignment in obj.get('assignments', []):
                pattern = assignment['pattern'] + '[#]' + ('[0-9]' * 10)
                pattern_re = fnmatch.translate(pattern)
                key = _alloc_key(pattern)
                priority = assignment['priority']

                _LOGGER.info('Assignment: %s - %s', pattern, priority)
                self.assignments[key].append(
                    (re.compile(pattern_re), priority, alloc)
                )

    def find_assignment(self, name):
        """Find allocation by matching app assignment."""
        _LOGGER.debug('Find assignment: %s', name)
        key = _alloc_key(name)

        if key in self.assignments:
            for assignment in self.assignments[key]:
                pattern_re, priority, alloc = assignment
                if pattern_re.match(name):
                    return (priority, alloc)

        _LOGGER.info('Default assignment.')
        return self.find_default_assignment(name)

    def find_default_assignment(self, name):
        """Finds (creates) default assignment."""
        alloc = self.cell.partitions[admin.DEFAULT_PARTITION].allocation

        unassigned = alloc.get_sub_alloc(admin.DEFAULT_TENANT)

        proid, _rest = name.split('.', 1)
        proid_alloc = unassigned.get_sub_alloc(proid)

        return 1, proid_alloc

    def load_apps(self):
        """Load application data."""
        apps = self.backend.list(z.SCHEDULED)
        for appname in apps:
            self.load_app(appname)

    def load_app(self, appname):
        """Load single application data."""
        # TODO: need to check if app is blacklisted.
        manifest = self.backend.get_default(z.path.scheduled(appname))
        if not manifest:
            self.cell.remove_app(appname)
            return

        priority, allocation = self.find_assignment(appname)
        if 'priority' in manifest and int(manifest['priority']) != -1:
            priority = int(manifest['priority'])

        # TODO: From scheduler perspective it is theoretically
        #                possible to update data retention timeout.
        data_retention = _get_data_retention(manifest)
        lease = _get_lease(manifest)

        app = self.cell.apps.get(appname, None)

        if app:
            app.priority = priority
            app.data_retention_timeout = data_retention
        else:
            demand = resources(manifest)
            affinity = manifest.get('affinity')
            affinity_limits = manifest.get('affinity_limits', None)
            identity_group = manifest.get('identity_group')
            schedule_once = manifest.get('schedule_once')
            app = scheduler.Application(appname, priority, demand,
                                        affinity=affinity,
                                        affinity_limits=affinity_limits,
                                        identity_group=identity_group,
                                        schedule_once=schedule_once,
                                        data_retention_timeout=data_retention,
                                        lease=lease)

        self.cell.add_app(allocation, app)

    def load_strategies(self):
        """Load affinity strategies for buckets."""
        pass

    def load_identity_groups(self):
        """Load identity groups."""
        names = set(self.backend.list(z.IDENTITY_GROUPS))
        extra = set(self.cell.identity_groups.keys()) - names
        _LOGGER.info('Removing identities: %r', extra)
        for name in extra:
            self.cell.remove_identity_group(name)

        for name in names:
            ident = self.backend.get_default(z.path.identity_group(name))
            if ident:
                count = ident.get('count', 0)
                _LOGGER.info('Configuring identity: %s, %s', name, count)
                self.cell.configure_identity_group(name, count)

    def restore_placements(self):
        """Restore placements after reload."""
        for servername in self.servers:

            try:
                placement_node = z.path.placement(servername)
                placed_apps = self.backend.list(placement_node)
            except be.ObjectNotFoundError:
                placed_apps = []

            server = self.servers[servername]
            server.remove_all()

            # Try to restore placement, if failed (e.g capacity of the
            # servername changed - remove.
            #
            # The servername does not need to be active at the time,
            # for applications will be moved from servers in DOWN state
            # on subsequent reschedule.
            for appname in placed_apps:
                if appname not in self.cell.apps:
                    continue

                app = self.cell.apps[appname]

                placement_data = self.backend.get_default(
                    z.path.placement(servername, appname)
                )

                # Placement is restored and assumed to be correct, so
                # force placement be specifying the server label.
                if placement_data is not None:
                    app.force_set_identity(placement_data.get('identity'))
                    app.placement_expiry = placement_data.get('expires', 0)

                assert app.allocation is not None
                _LOGGER.info('Restore placement %s => %s', appname, servername)
                if not server.put(app):
                    _LOGGER.info('Failed to restore placement %s => %s',
                                 appname, servername)
                    app.evicted = True

    def adjust_server_presence(self, server_presence):
        """Adjust server presence, update state and valid_until accordingly."""
        servers = dict(presence.parse_server(node)
                       for node in sorted(server_presence))

        for servername, server in self.servers.items():
            presence_id = servers.get(servername)
            if server.presence_id and server.presence_id != presence_id:
                # Server had presence and doesn't have now or presence changed.
                # If server presence changed, handle it as down first, then up.
                _LOGGER.info('Server is down: %s (old presence id: %s)',
                             servername, server.presence_id)
                server.presence_id = None
                self.adjust_server_state(server)
                self.adjust_server_valid_until(server)

        for servername, presence_id in servers.items():
            server = self.servers.get(servername)
            if not server or server.presence_id != presence_id:
                # Server is new or its presence changed.
                _LOGGER.info('Server is up: %s (new presence id: %s)',
                             servername, presence_id)
                self.reload_server(servername)
                # Adjust only if reload didn't remove server or load it as new.
                if (servername in self.servers and
                        server == self.servers[servername]):
                    server.presence_id = presence_id
                    self.adjust_server_state(server)
                    self.adjust_server_valid_until(server)

    def check_integrity(self):
        """Checks integrity of scheduler state vs. real."""
        return True

    def save_state_reports(self):
        """Prepare scheduler reports and save them to ZooKeeper."""
        for report_type in ('servers', 'allocations', 'apps'):
            _LOGGER.info('Saving scheduler report "%s" to ZooKeeper',
                         report_type)
            report = getattr(reports, report_type)(self.cell)
            self.backend.put(
                z.path.state_report(report_type),
                reports.serialize_dataframe(report)
            )
