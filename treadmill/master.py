"""Treadmill master process."""


# Disable too many lines in module warning.
#
# pylint: disable=C0302

import collections
import logging
import fnmatch
import os
import time
import threading
import re

import kazoo

from . import appevents
from . import sysinfo
from . import utils
from . import zkutils
from . import exc
from . import zknamespace as z
from . import scheduler

from .apptrace import events as traceevents

_LOGGER = logging.getLogger(__name__)


def _app_node(app_id, existing=True):
    """Returns node path given app id."""
    path = os.path.join(z.SCHEDULED, app_id)
    if not existing:
        path = path + '#'
    return path


def resources(data):
    """Convert resource demand/capacity spec into resource vector."""
    parsers = {
        'memory': utils.megabytes,
        'disk': utils.megabytes,
        'cpu': utils.cpu_units
    }

    return [parsers[k](data.get(k, 0)) for k in ['memory', 'cpu', 'disk']]


def get_data_retention(data):
    """Returns data retention timeout in seconds."""
    if 'data_retention_timeout' in data:
        return utils.to_seconds(data['data_retention_timeout'])
    else:
        return None


def get_lease(data):
    """Returns lease attribute converted to seconds."""
    return utils.to_seconds(data.get('lease', '0s'))


def time_past(when):
    """Check if time past the given timestamp."""
    return time.time() > when


# ACL which allows all servers in the cell to full control over node.
#
# Set in /tasks, /servers
_SERVERS_ACL = zkutils.make_role_acl('servers', 'rwcd')
# Delete only servers ACL
_SERVERS_ACL_DEL = zkutils.make_role_acl('servers', 'd')

# Timer interval to reevaluate time events (seconds).
# TIMER_INTERVAL = 60

# Time interval between running the scheduler (seconds).
SCHEDULER_INTERVAL = 2

# Interval to sleep before checking if there is new event in the queue.
CHECK_EVENT_INTERVAL = 0.5

# Check integrity of the scheduler every 5 minutes.
INTEGRITY_INTERVAL = 5 * 60

# Check for reboots every hour.
REBOOT_CHECK_INTERVAL = 60 * 60

# Max number of events to process before checking if scheduler is due.
EVENT_BATCH_COUNT = 20

# Delay between re-establishing collection watch (seconds).
# COLLECTION_EVENT_DELAY = 0.5


class Master(object):
    """Treadmill master scheduler."""

    def __init__(self, zkclient, cellname, events_dir=None):
        self.zkclient = zkclient
        self.cell = scheduler.Cell(cellname)
        self.events_dir = events_dir

        self.buckets = dict()
        self.servers = dict()
        self.allocations = dict()
        self.assignments = dict()
        self.partitions = dict()

        self.queue = collections.deque()
        self.up_to_date = False
        self.exit = False
        # Signals that processing of a given event.
        self.process_complete = dict()

    def create_rootns(self):
        """Create root nodes and set appropriate acls."""

        root_ns = {
            '/': None,
            z.ALLOCATIONS: None,
            z.APPMONITORS: None,
            z.BUCKETS: None,
            z.CELL: None,
            z.IDENTITY_GROUPS: None,
            z.PLACEMENT: None,
            z.PARTITIONS: None,
            z.SCHEDULED: [_SERVERS_ACL_DEL],
            z.SCHEDULER: None,
            z.SERVERS: None,
            z.STRATEGIES: None,
            z.TASKS: None,
            z.VERSION_ID: None,
            z.ZOOKEEPER: None,
            z.BLACKEDOUT_SERVERS: [_SERVERS_ACL],
            z.ENDPOINTS: [_SERVERS_ACL],
            z.path.endpoint_proid('root'): [_SERVERS_ACL],
            z.EVENTS: [_SERVERS_ACL],
            z.RUNNING: [_SERVERS_ACL],
            z.SERVER_PRESENCE: [_SERVERS_ACL],
            z.VERSION: [_SERVERS_ACL],
            z.REBOOTS: [_SERVERS_ACL],
        }

        for path, acl in root_ns.items():
            zkutils.ensure_exists(self.zkclient, path, acl)

    def load_cell(self):
        """Construct cell from top level buckets."""
        buckets = self.zkclient.get_children(z.CELL)
        self.cell.reset_children()
        for bucketname in buckets:
            _LOGGER.info('adding bucket to cell: %s', bucketname)
            self.cell.add_node(self.buckets[bucketname])

    def load_partitions(self):
        """Load partitions."""
        # Create default partition.
        self.cell.partitions[None] = scheduler.Partition()

        partitions = self.zkclient.get_childrent(z.PARTITIONS)
        for partition in partitions:
            self.load_partition(partition)

    def load_partition(self, partition):
        """Load partition."""
        try:
            data = zkutils.get(self.zkclient, z.path.partition(partition))
            self.cell.partitions[partition] = scheduler.Partition(
                max_server_uptime=data.get('server_uptime'),
                max_lease=data.get('max_lease'),
                threshold=data.get('threshold'),
            )

        except kazoo.client.NoNodeError:
            _LOGGER.warn('Partition node not found: %s', partition)

    def load_buckets(self):
        """Load bucket hierarchy."""
        buckets = self.zkclient.get_children(z.BUCKETS)
        for bucketname in buckets:
            self.load_bucket(bucketname)

    def load_bucket(self, bucketname):
        """Load bucket info, assume parent is already created."""
        # Do not load twice.
        if bucketname in self.buckets:
            return self.buckets[bucketname]

        _LOGGER.info('loading bucket: %s', bucketname)
        data = zkutils.get_default(self.zkclient,
                                   z.path.bucket(bucketname),
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

    def load_servers(self, readonly=False):
        """Load server topology."""
        servers = self.zkclient.get_children(z.SERVERS)
        for servername in servers:
            self.load_server(servername, readonly)

    def load_server(self, servername, readonly=False):
        """Load individual server."""
        try:
            data = zkutils.get(self.zkclient, z.path.server(servername))
            if not data:
                # The server is configured, but never reported it's capacity.
                _LOGGER.info('No capacity detected: %s',
                             z.path.server(servername))
                return

            assert 'parent' in data
            parentname = data['parent']
            label = data.get('label', None)
            up_since = data.get('up_since', int(time.time()))

            partition = self.cell.partitions[label]
            server = scheduler.Server(
                servername,
                resources(data),
                valid_until=partition.valid_until(up_since),
                label=label,
                traits=data.get('traits', 0)
            )

            parent = self.buckets.get(parentname)
            if not parent:
                _LOGGER.warn('Server parent does not exist: %s/%s',
                             servername, parentname)
                return

            self.buckets[parentname].add_node(server)
            self.servers[servername] = server
            assert server.parent == self.buckets[parentname]

            if not readonly:
                zkutils.ensure_exists(self.zkclient,
                                      z.path.placement(servername),
                                      acl=[_SERVERS_ACL])

            self.adjust_server_state(servername, readonly)

        except kazoo.client.NoNodeError:
            _LOGGER.warn('Server node not found: %s', servername)

    def remove_server(self, servername):
        """Remove server from scheduler."""
        if servername not in self.servers:
            return

        server = self.servers[servername]
        server.remove_all()
        server.parent.remove_node(server)

        del self.servers[servername]

    def reload_servers(self, servers):
        """Reload servers in the list."""
        for server in servers:
            self.reload_server(server)

    def reload_server(self, servername):
        """Reload individual server."""
        _LOGGER.info('reloading server: %s', servername)
        if servername not in self.servers:
            # This server was never loaded.
            self.load_server(servername)
            return

        current_server = self.servers[servername]
        # Check if server is same
        try:
            data = zkutils.get(self.zkclient, z.path.server(servername))
            if not data:
                # The server is configured, but never reported it's capacity.
                self.remove_server(servername)
                return

            # TODO: need better error handling.
            assert 'parent' in data
            assert data['parent'] in self.buckets

            label = data.get('label')

            up_since = data.get('up_since', time.time())
            partition = self.cell.partitions[label]

            server = scheduler.Server(
                servername,
                resources(data),
                valid_until=partition.valid_until(up_since),
                label=label,
                traits=data.get('traits', 0)
            )

            parent = self.buckets[data['parent']]
            # TODO: assume that bucket topology is constant, e.g.
            #                rack can never change buiding. If this does not
            #                hold, comparing parents is not enough, need to
            #                compare recursively all the way up.
            if (current_server.is_same(server) and
                    current_server.parent == parent):
                # Nothing changed, no need to update anything.
                _LOGGER.info('server is same, keeping old.')
                current_server.valid_until = server.valid_until
            else:
                # Something changed - clear everything and re-register server
                # as new.
                _LOGGER.info('server modified, replacing.')
                self.remove_server(servername)
                self.load_server(servername)

        except kazoo.client.NoNodeError:
            self.remove_server(servername)
            _LOGGER.warn('Server node not found: %s', servername)

    def adjust_server_state(self, servername, readonly=False):
        """Set server state."""
        server = self.servers.get(servername)
        if not server:
            return

        is_up = self.zkclient.exists(z.path.server_presence(servername))

        placement_node = z.path.placement(servername)

        # Restore state as it was stored in server placement node.
        #
        # zkutils.get_default return tuple if need_metadata is True, default it
        # is False, so it will return dict. pylint complains about it,
        # and it should be fixed in zkutils.
        #
        # pylint: disable=R0204
        state_since = zkutils.get_default(self.zkclient, placement_node)
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
        if not readonly:
            zkutils.put(self.zkclient, placement_node,
                        {'state': state.value, 'since': since})

    def load_allocations(self):
        """Load allocations and assignments map."""
        data = zkutils.get_default(self.zkclient, z.ALLOCATIONS, default={})
        if not data:
            return

        for obj in data:
            label = obj.get('label')
            name = obj['name']

            _LOGGER.info('Loading allocation: %s, label: %s', name, label)

            alloc = self.cell.partitions[label].allocation
            for part in re.split('[/:]', name):
                alloc = alloc.get_sub_alloc(part)
                capacity = resources(obj)
                alloc.update(capacity, obj['rank'], obj.get('max-utilization'))

            for assignment in obj.get('assignments', []):
                pattern = assignment['pattern'] + '[#]' + ('[0-9]' * 10)
                priority = assignment['priority']
                _LOGGER.info('Assignment: %s - %s', pattern, priority)
                self.assignments[pattern] = (priority, alloc)

    def find_assignment(self, name):
        """Find allocation by matching app assignment."""
        _LOGGER.debug('Find assignment: %s', name)
        assignments = reversed(sorted(self.assignments.items()))

        for pattern, assignment in assignments:
            if fnmatch.fnmatch(name, pattern):
                _LOGGER.info('Found: %s, assignment: %s', pattern, assignment)
                return assignment

        _LOGGER.info('Default assignment.')
        return self.find_default_assignment(name)

    def find_default_assignment(self, name):
        """Finds (creates) default assignment."""
        alloc = self.cell.partitions[None].allocation
        unassigned = alloc.get_sub_alloc('_default')
        proid, _rest = name.split('.', 1)
        return 1, unassigned.get_sub_alloc(proid)

    def load_apps(self, readonly=False):
        """Load application data."""
        apps = self.zkclient.get_children(z.SCHEDULED)
        for appname in apps:
            self.load_app(appname, readonly)

        self.restore_placements()

    def load_app(self, appname, readonly=False):
        """Load single application data."""
        # TODO: need to check if app is blacklisted.
        manifest = zkutils.get_default(self.zkclient,
                                       z.path.scheduled(appname))
        if not manifest:
            self.cell.remove_app(appname)
            return

        priority, allocation = self.find_assignment(appname)
        if 'priority' in manifest and int(manifest['priority']) != -1:
            priority = int(manifest['priority'])

        # TODO: From scheduler perspective it is theoretically
        #                possible to update data retention timeout.
        data_retention = get_data_retention(manifest)
        lease = get_lease(manifest)

        app = self.cell.apps.get(appname, None)
        if not readonly:
            self._create_task(appname)

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
        names = set(self.zkclient.get_children(z.IDENTITY_GROUPS))
        extra = set(self.cell.identity_groups.keys()) - names
        _LOGGER.info('Removing identities: %r', extra)
        for name in extra:
            self.cell.remove_identity_group(name)

        for name in names:
            ident = zkutils.get_default(self.zkclient,
                                        z.path.identity_group(name))
            if ident:
                count = ident.get('count', 0)
                _LOGGER.info('Configuring identity: %s, %s', name, count)
                self.cell.configure_identity_group(name, count)

    def restore_placements(self):
        """Restore placements after reload."""
        integrity = collections.defaultdict(list)

        for servername in self.servers:
            try:
                placement_node = z.path.placement(servername)
                placed_apps = self.zkclient.get_children(placement_node)
            except kazoo.exceptions.NoNodeError:
                placed_apps = []

            for appname in placed_apps:
                appnode = z.path.placement(servername, appname)
                if appname not in self.cell.apps:
                    # Stale app - safely ignored.
                    zkutils.ensure_deleted(self.zkclient, appnode)
                else:
                    # Try to restore placement, if failed (e.g capacity of the
                    # servername changed - remove.
                    #
                    # The servername does not need to be active at the time,
                    # for applications will be moved from servers in DOWN state
                    # on subsequent reschedule.
                    app = self.cell.apps[appname]
                    integrity[appname].append(servername)

                    server = self.servers[servername]

                    # Placement is restored and assumed to be correct, so
                    # force placement be specifying the server label.
                    assert app.allocation is not None
                    if server.put(app):
                        _LOGGER.info('Restore placement: %s => %s',
                                     appname, servername)
                    else:
                        _LOGGER.info('Failed to restore placement: %s => %s',
                                     appname, servername)
                        zkutils.ensure_deleted(self.zkclient, appnode)
                        # Check if app is marked to be scheduled once. If it is
                        # remove the app.
                        if app.schedule_once:
                            _LOGGER.info('Removing scheduled once app: %s',
                                         appname)
                            zkutils.ensure_deleted(self.zkclient,
                                                   z.path.scheduled(appname))
                            self.cell.remove_app(appname)

        for appname, servers in integrity.items():
            if len(servers) > 1:
                _LOGGER.warn('Integrity error: %s placed on %r',
                             appname, servers)
                for servername in servers:
                    zkutils.ensure_deleted(
                        self.zkclient,
                        z.path.placement(servername, appname)
                    )
                    self.servers[servername].remove(appname)

    def load_placement_data(self):
        """Restore app identities."""
        for appname, app in self.cell.apps.items():
            if app.server:
                placement_data = zkutils.get_default(
                    self.zkclient, z.path.placement(app.server, appname))

                if placement_data is not None:
                    app.force_set_identity(placement_data.get('identity'))
                    app.placement_expiry = placement_data.get('expires', 0)

    def adjust_presence(self, servers):
        """Given current presence set, adjust status."""
        down_servers = set([
            servername for servername in self.servers
            if self.servers[servername].state is scheduler.State.down])
        up_servers = set(self.servers.keys()) - down_servers

        # Server was up, but now is down.
        for servername in up_servers - servers:
            _LOGGER.info('Server is down: %s', servername)
            self.adjust_server_state(servername)
        # Server was down, and now is up.
        for servername in down_servers & servers:
            # Make sure that new server capacity and traits are up to
            # date.
            _LOGGER.info('Server is up: %s', servername)
            self.reload_server(servername)
            self.adjust_server_state(servername)

    def check_placement_integrity(self):
        """Check integrity of app placement."""
        app2server = dict()
        servers = self.zkclient.get_children(z.PLACEMENT)
        for server in servers:
            apps = self.zkclient.get_children(z.path.placement(server))
            for app in apps:
                if app not in app2server:
                    app2server[app] = server
                    continue

                _LOGGER.critical('Duplicate placement: %s: (%s, %s)',
                                 app, app2server[app], server)

                # Check the cell datamodel.
                correct_placement = self.cell.apps[app].server
                _LOGGER.critical('Correct placement: %s', correct_placement)

                # If correct placement is neither, something is seriously
                # corrupted, no repair possible.
                assert correct_placement in [app2server[app], server]

                if server != correct_placement:
                    _LOGGER.critical('Removing incorrect placement: %s/%s',
                                     server, app)
                    zkutils.ensure_deleted(
                        self.zkclient, z.path.placement(server, app))

                if app2server[app] != correct_placement:
                    _LOGGER.critical('Removing incorrect placement: %s/%s',
                                     app2server[app], app)
                    zkutils.ensure_deleted(
                        self.zkclient, z.path.placement(app2server[app], app))

        # Cross check that all apps in the model are recorded in placement.
        success = True
        for appname, app in self.cell.apps.items():
            if app.server:
                if appname not in app2server:
                    _LOGGER.critical('app missing from placement: %s', appname)
                    success = False
                else:
                    if app.server != app2server[appname]:
                        _LOGGER.critical(
                            'corrupted placement %s: expected: %s, actual: %s',
                            appname, app.server, app2server[appname]
                        )
                        success = False

        assert success, 'Placement integrity failed.'

    def check_integrity(self):
        """Checks integrity of scheduler state vs. real."""
        return True

    @exc.exit_on_unhandled
    def process(self, event):
        """Process state change event."""
        path, children = event
        _LOGGER.info('processing: %r', event)
        callbacks = {
            z.SERVER_PRESENCE: self.process_server_presence,
            z.SCHEDULED: self.process_scheduled,
            z.EVENTS: self.process_events,
        }

        assert path in callbacks

        callbacks[path](children)

        _LOGGER.info('waiting for completion.')
        self.process_complete[path].set()
        self.up_to_date = False

        _LOGGER.info('done processing events.')

    def process_scheduled(self, scheduled):
        """Callback invoked when on scheduling changes."""
        current = set(self.cell.apps.keys())
        target = set(scheduled)

        for appname in current - target:
            app = self.cell.apps[appname]
            if app.server:
                zkutils.ensure_deleted(self.zkclient,
                                       z.path.placement(app.server, appname))
            if self.events_dir:
                appevents.post(
                    self.events_dir,
                    traceevents.DeletedTraceEvent(
                        instanceid=appname
                    )
                )
            self.cell.remove_app(appname)

        for appname in target - current:
            self.load_app(appname)

    def process_server_presence(self, servers):
        """Callback invoked when server presence is modified."""
        self.adjust_presence(set(servers))

    def process_events(self, events):
        """Callback invoked on state change/admin event."""
        # Events are sequential nodes in the form <prio>-<event>-<seq #>
        #
        # They are processed in order of (prio, seq_num, event)
        ordered = sorted([tuple([event.split('-')[i] for i in [0, 2, 1]])
                          for event in events
                          if re.match(r'\d+\-\w+\-\d+$', event)])

        for prio, seq, resource in ordered:
            _LOGGER.info('event: %s %s %s', prio, seq, resource)
            node_name = '-'.join([prio, resource, seq])
            if resource == 'allocations':
                # TODO: changing allocations has potential of complete
                #                reshuffle, so while ineffecient, reload
                #                all apps as well.
                self.load_allocations()
                self.load_apps()
            elif resource == 'apps':
                # The event node contains list of apps to be re-evaluated.
                apps = zkutils.get_default(
                    self.zkclient,
                    z.path.event(node_name),
                    default=[])
                for app in apps:
                    self.load_app(app)
            elif resource == 'cell':
                self.load_cell()
            elif resource == 'servers':
                servers = zkutils.get_default(
                    self.zkclient,
                    z.path.event(node_name),
                    default=[])
                if not servers:
                    # If not specified, reload all. Use union of servers in
                    # the model and in zookeeper.
                    servers = (set(self.servers.keys()) ^
                               set(self.zkclient.get_children(z.SERVERS)))
                self.reload_servers(servers)
            elif resource == 'identity_groups':
                self.load_identity_groups()
            else:
                _LOGGER.warn('Unsupported event resource: %s', resource)

        for node in events:
            _LOGGER.info('Deleting event: %s', z.path.event(node))
            zkutils.ensure_deleted(self.zkclient, z.path.event(node))

    def watch(self, path):
        """Constructs a watch on a given path."""

        @exc.exit_on_unhandled
        @self.zkclient.ChildrenWatch(path)
        def _watch(children):
            """Watch children events."""
            _LOGGER.debug('watcher begin: %s', path)
            # On first invocation, we create event and do not wait on it,
            # as the event loop not started yet.
            #
            # On subsequent calls, wait for processing to complete before
            # renewing the watch, to avoid busy loops.
            if path in self.process_complete:
                self.process_complete[path].clear()

            self.queue.append((path, children))

            if path in self.process_complete:
                _LOGGER.debug('watcher waiting for completion: %s', path)
                self.process_complete[path].wait()
            else:
                self.process_complete[path] = threading.Event()

            _LOGGER.debug('watcher finished: %s', path)
            return True

    @exc.exit_on_unhandled
    def run_real(self):
        """Loads cell state from Zookeeper."""
        self.create_rootns()
        self.load_buckets()
        self.load_cell()
        self.load_servers()
        self.load_allocations()
        self.load_strategies()
        self.load_apps()
        self.load_identity_groups()
        self.load_placement_data()

        # Must be called last
        self.load_schedule()

        self.watch(z.SERVER_PRESENCE)
        self.watch(z.SCHEDULED)
        self.watch(z.EVENTS)

        last_sched_time = time.time()
        last_integrity_check = 0
        last_reboot_check = 0
        while not self.exit:
            queue_empty = False
            for _idx in range(0, EVENT_BATCH_COUNT):
                try:
                    event = self.queue.popleft()
                    self.process(event)
                except IndexError:
                    queue_empty = True
                    break
            try:
                if time_past(last_sched_time + SCHEDULER_INTERVAL):
                    last_sched_time = time.time()
                    if not self.up_to_date:
                        self.reschedule()
                        self.check_placement_integrity()

                if time_past(last_integrity_check + INTEGRITY_INTERVAL):
                    assert self.check_integrity()
                    last_integrity_check = time.time()
            except AssertionError:
                raise

            if time_past(last_reboot_check + REBOOT_CHECK_INTERVAL):
                self.check_reboot()
                last_reboot_check = time.time()

            if queue_empty:
                time.sleep(CHECK_EVENT_INTERVAL)

    @exc.exit_on_unhandled
    def run(self):
        """Runs the master (once it is elected leader)."""
        self.zkclient.ensure_path('/master-election')
        me = '%s.%d' % (sysinfo.hostname(), os.getpid())
        lock = self.zkclient.Lock('/master-election', me)
        _LOGGER.info('Waiting for leader lock.')
        with lock:
            self.run_real()

    def _schedule_reboot(self, servername):
        """Schedule server reboot."""
        zkutils.ensure_exists(self.zkclient,
                              z.path.reboot(servername),
                              acl=[_SERVERS_ACL_DEL])

    def check_reboot(self):
        """Identify all expired servers."""
        self.cell.resolve_reboot_conflicts()

        now = time.time()

        # expired servers rebooted unconditionally, as they are no use anumore.
        for name, server in self.servers.items():
            if now > server.valid_until:
                _LOGGER.info(
                    'Expired: %s at %s',
                    name,
                    server.valid_until
                )
                self._schedule_reboot(name)
                continue
            # For servers that have < 1 day (default app least) time - if apps
            # are expired, reboot.
            if now + scheduler.DEFAULT_APP_LEASE > server.valid_until:
                latest_app_expiry = server.latest_app_expiry()
                if now > latest_app_expiry:
                    _LOGGER.info(
                        'All app expired: %s at %s',
                        name,
                        server.valid_until
                    )
                    self._schedule_reboot(name)
                    continue

    def _placement_data(self, app):
        """Return placement data for given app."""
        return {
            'identity': self.cell.apps[app].identity,
            'expires': self.cell.apps[app].placement_expiry
        }

    def load_schedule(self):
        """Run scheduler first time and update scheduled data."""
        placement = self.cell.schedule()

        for servername, server in self.cell.members().items():
            placement_node = z.path.placement(servername)
            zkutils.ensure_exists(self.zkclient,
                                  placement_node,
                                  acl=[_SERVERS_ACL])

            current = set(self.zkclient.get_children(placement_node))
            correct = set(server.apps.keys())

            for app in current - correct:
                _LOGGER.info('Unscheduling: %s - %s', servername, app)
                zkutils.ensure_deleted(self.zkclient,
                                       os.path.join(placement_node, app))
            for app in correct - current:
                _LOGGER.info('Scheduling: %s - %s,%s',
                             servername, app, self.cell.apps[app].identity)

                placement_data = self._placement_data(app)
                zkutils.put(self.zkclient,
                            os.path.join(placement_node, app),
                            placement_data,
                            acl=[_SERVERS_ACL])
                self._update_task(app, servername)

        # Store latest placement as reference.
        zkutils.put(self.zkclient, z.path.placement(), placement)
        self.up_to_date = True

    def reschedule(self):
        """Run scheduler and adjust placement."""
        placement = self.cell.schedule()

        # Filter out placement records where nothing changed.
        changed_placement = [
            (app, before, exp_before, after, exp_after)
            for app, before, exp_before, after, exp_after in placement
            if before != after or exp_before != exp_after
        ]

        # We run two loops. First - remove all old placement, before creating
        # any new ones. This ensures that in the event of loop interruption
        # for anyreason (like Zookeeper connection lost or master restart)
        # there are no duplicate placements.
        for app, before, exp_before, after, exp_after in changed_placement:
            if before and before != after:
                _LOGGER.info('Unscheduling: %s - %s', before, app)
                zkutils.ensure_deleted(
                    self.zkclient,
                    z.path.placement(before, app))

        for app, before, exp_before, after, exp_after in changed_placement:
            placement_data = self._placement_data(app)
            if after:
                _LOGGER.info('Scheduling: %s - %s,%s, expires at: %s',
                             after,
                             app,
                             self.cell.apps[app].identity,
                             exp_after)

                zkutils.put(
                    self.zkclient,
                    z.path.placement(after, app),
                    placement_data,
                    acl=[_SERVERS_ACL])
                self._update_task(app, after)
            else:
                self._update_task(app, None)

        self._unschedule_evicted()

        # Store latest placement as reference.
        zkutils.put(self.zkclient, z.path.placement(), placement)
        self.up_to_date = True

    def _unschedule_evicted(self):
        """Delete schedule once and evicted apps."""
        # Apps that were evicted and are configured to be scheduled once
        # should be removed.
        #
        # Remove will trigger rescheduling which will be harmless but
        # strictly speaking unnecessary.
        for appname, app in self.cell.apps.items():
            if app.schedule_once and app.evicted:
                _LOGGER.info('Removing schedule_once/evicted app: %s',
                             appname)
                # TODO: need to publish trace event.
                zkutils.ensure_deleted(self.zkclient,
                                       z.path.scheduled(appname))

    def _create_task(self, appname):
        """Ensures that task is created for an app."""
        zkutils.ensure_exists(self.zkclient, z.path.task(appname),
                              acl=[_SERVERS_ACL])

    def _update_task(self, appname, server):
        """Creates/updates application task with the new placement."""
        # Servers in the cell have full control over task node.
        if self.events_dir:
            if server:
                appevents.post(
                    self.events_dir,
                    traceevents.ScheduledTraceEvent(
                        instanceid=appname,
                        where=server
                    )
                )
            else:
                appevents.post(
                    self.events_dir,
                    traceevents.PendingTraceEvent(
                        instanceid=appname
                    )
                )

    def _abort_task(self, appname, exception):
        """Set task into aborted state in case of scheduling error."""
        if self.events_dir:
            appevents.post(
                self.events_dir,
                traceevents.AbortedTraceEvent(
                    instanceid=appname,
                    why=type(exception).__name__
                )
            )


# master/scheduler "API"

def create_event(zkclient, priority, event, payload):
    """Places event on the event queue."""
    assert 0 <= priority <= 100
    node_path = z.path.event(
        '%(priority)03d-%(event)s-' % {'priority': priority, 'event': event})

    return os.path.basename(
        zkutils.put(zkclient, node_path, payload, acl=[_SERVERS_ACL],
                    sequence=True))


def create_apps(zkclient, app_id, app, count):
    """Schedules new apps."""
    app_ids = []
    acl = zkutils.make_role_acl('servers', 'rwcd')
    for _idx in range(0, count):
        node_path = zkutils.put(zkclient,
                                _app_node(app_id, existing=False),
                                app,
                                sequence=True,
                                acl=[acl])
        app_ids.append(os.path.basename(node_path))

    return app_ids


def delete_apps(zkclient, app_ids):
    """Unschedules apps."""
    for app_id in app_ids:
        zkutils.ensure_deleted(zkclient, _app_node(app_id))


def get_app(zkclient, app_id):
    """Return scheduled app details by app_id."""
    return zkutils.get_default(zkclient, _app_node(app_id))


def list_scheduled_apps(zkclient):
    """List all scheduled apps."""
    scheduled = zkclient.get_children(z.SCHEDULED)
    return scheduled


def list_running_apps(zkclient):
    """List all scheduled apps."""
    running = zkclient.get_children(z.RUNNING)
    return running


def update_app_priorities(zkclient, updates):
    """Updates app priority."""
    for app_id, priority in updates.items():
        assert 0 <= priority <= 100

        app = get_app(zkclient, app_id)
        app['priority'] = priority
        zkutils.update(zkclient, _app_node(app_id), app)

    create_event(zkclient, 1, 'apps', list(updates.keys()))


def create_bucket(zkclient, bucket_id, parent_id, traits=0):
    """Creates bucket definition in Zookeeper."""
    data = {
        'traits': traits,
        'parent': parent_id
    }
    zkutils.put(zkclient, z.path.bucket(bucket_id), data, check_content=True)


def update_bucket_traits(zkclient, bucket_id, traits):
    """Updates bucket traits."""
    data = get_bucket(zkclient, bucket_id)
    data['traits'] = traits
    zkutils.put(zkclient, z.path.bucket(bucket_id), data, check_content=True)


def get_bucket(zkclient, bucket_id):
    """Return bucket definition in Zookeeper."""
    return zkutils.get(zkclient, z.path.bucket(bucket_id))


def delete_bucket(zkclient, bucket_id):
    """Deletes bucket definition from Zoookeeper."""
    zkutils.ensure_deleted(zkclient, z.path.bucket(bucket_id))


def list_buckets(zkclient):
    """List all buckets."""
    return sorted(zkclient.get_children(z.BUCKETS))


def create_server(zkclient, server_id, parent_id):
    """Creates server definition in Zookeeper."""
    server_node = z.path.server(server_id)
    server_acl = zkutils.make_host_acl(server_id, 'rwcd')

    zkutils.ensure_exists(zkclient, server_node, acl=[server_acl])

    # zkutils.get return dict/tuple if need_metadata is true.
    #
    # pylint: disable=R0204
    data = zkutils.get(zkclient, server_node)
    if parent_id:
        if not data:
            data = {'parent': parent_id}
        else:
            data['parent'] = parent_id

    _LOGGER.info('Creating server node %s with data %r and ACL %r',
                 server_node, data, server_acl)
    if zkutils.put(zkclient, server_node, data,
                   acl=[server_acl], check_content=True):
        create_event(zkclient, 0, 'servers', [server_id])


def list_servers(zkclient):
    """List all servers."""
    return sorted(zkclient.get_children(z.SERVERS))


def update_server_attrs(zkclient, server_id, traits, label):
    """Updates server traits."""
    node = z.path.server(server_id)
    data = zkutils.get(zkclient, node)
    data['traits'] = traits
    data['label'] = label

    if zkutils.update(zkclient, node, data, check_content=True):
        create_event(zkclient, 0, 'servers', [server_id])


def update_server_capacity(zkclient, server_id,
                           memory=None, cpu=None, disk=None):
    """Update server capacity."""
    node = z.path.server(server_id)
    data = zkutils.get(zkclient, node)
    if memory:
        data['memory'] = memory
    if cpu:
        data['cpu'] = cpu
    if disk:
        data['disk'] = disk

    if zkutils.update(zkclient, node, data, check_content=True):
        create_event(zkclient, 0, 'servers', [server_id])


def update_server_parent(zkclient, server_id, parent_id):
    """Update server parent."""
    node = z.path.server(server_id)
    data = zkutils.get(zkclient, node)
    data['parent'] = parent_id

    if zkutils.update(zkclient, node, data, check_content=True):
        create_event(zkclient, 0, 'servers', [server_id])


def delete_server(zkclient, server_id):
    """Delete the server in Zookeeper."""
    zkutils.ensure_deleted(zkclient, z.path.server(server_id))
    zkutils.ensure_deleted(zkclient, z.path.placement(server_id))
    create_event(zkclient, 0, 'servers', [server_id])


def get_server(zkclient, server_id):
    """Return server object."""
    return zkutils.get(zkclient, z.path.server(server_id))


def cell_insert_bucket(zkclient, bucket_id):
    """Add bucket to the cell."""
    if not zkclient.exists(z.path.cell(bucket_id)):
        zkutils.ensure_exists(zkclient, z.path.cell(bucket_id))
        create_event(zkclient, 0, 'cell', None)


def cell_remove_bucket(zkclient, bucket_id):
    """Remove bucket from the cell."""
    if zkclient.exists(z.path.cell(bucket_id)):
        zkutils.ensure_deleted(zkclient, z.path.cell(bucket_id))
        create_event(zkclient, 0, 'cell', None)


def cell_buckets(zkclient):
    """Return list of top level cell buckets."""
    return sorted(zkclient.get_children(z.CELL))


def appmonitors(zkclient):
    """Return list of app monitors ids."""
    return sorted(zkclient.get_children(z.path.appmonitor()))


def get_appmonitor(zkclient, monitor_id, raise_notfound=False):
    """Return app monitor given id."""
    try:
        data = zkutils.get(zkclient, z.path.appmonitor(monitor_id))
        data['_id'] = monitor_id
        return data
    except kazoo.client.NoNodeError:
        _LOGGER.info('App monitor does not exist: %s', monitor_id)
        if raise_notfound:
            raise
        else:
            return None


def update_appmonitor(zkclient, monitor_id, count):
    """Configures app monitor."""
    node = z.path.appmonitor(monitor_id)
    data = {'count': count}
    zkutils.put(zkclient, node, data, check_content=True)


def delete_appmonitor(zkclient, monitor_id):
    """Deletes app monitor."""
    zkutils.ensure_deleted(zkclient, z.path.appmonitor(monitor_id))


def identity_groups(zkclient):
    """List all identity groups."""
    return sorted(zkclient.get_children(z.IDENTITY_GROUPS))


def get_identity_group(zkclient, ident_group_id):
    """Return app monitor given id."""
    data = zkutils.get(zkclient, z.path.identity_group(ident_group_id))
    data['_id'] = ident_group_id
    return data


def update_identity_group(zkclient, ident_group_id, count):
    """Updates identity group count."""
    node = z.path.identity_group(ident_group_id)
    data = {'count': count}
    if zkutils.put(zkclient,
                   node,
                   data,
                   check_content=True,
                   acl=[_SERVERS_ACL]):
        create_event(zkclient, 0, 'identity_groups', [ident_group_id])


def delete_identity_group(zkclient, ident_group_id):
    """Delete identity group."""
    node = z.path.identity_group(ident_group_id)
    zkutils.ensure_deleted(zkclient, node)
    create_event(zkclient, 0, 'identity_groups', [ident_group_id])
