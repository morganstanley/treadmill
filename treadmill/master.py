"""Treadmill master process.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# Disable too many lines in module warning.
#
# pylint: disable=C0302

import collections
import fnmatch
import logging
import os
import re
import time

import kazoo
import six

from treadmill import admin
from treadmill import appevents
from treadmill import reports
from treadmill import scheduler
from treadmill import utils
from treadmill import zknamespace as z
from treadmill import zkutils

from treadmill.appcfg import abort as app_abort
from treadmill.apptrace import events as traceevents

_LOGGER = logging.getLogger(__name__)


def _app_node(app_id, existing=True):
    """Returns node path given app id."""
    path = os.path.join(z.SCHEDULED, app_id)
    if not existing:
        path = path + '#'
    return path


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


def get_data_retention(data):
    """Returns data retention timeout in seconds."""
    data_retention_timeout = data.get('data_retention_timeout')
    if data_retention_timeout is not None:
        return utils.to_seconds(data_retention_timeout)
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
# Set in /finished, /servers
_SERVERS_ACL = zkutils.make_role_acl('servers', 'rwcda')
# Delete only servers ACL
_SERVERS_ACL_DEL = zkutils.make_role_acl('servers', 'd')

# Timer interval to reevaluate time events (seconds).
# TIMER_INTERVAL = 60

# Time interval between running the scheduler (seconds).
SCHEDULER_INTERVAL = 2

# Save reports on the scheduler state to ZooKeeper every minute.
STATE_REPORT_INTERVAL = 60

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

    def __init__(self, zkclient, cellname, events_dir=None, readonly=False):
        self.zkclient = zkclient
        self.cell = scheduler.Cell(cellname)
        self.events_dir = events_dir
        self.readonly = readonly

        self.buckets = dict()
        self.servers = dict()
        self.allocations = dict()
        self.assignments = collections.defaultdict(list)
        self.partitions = dict()

        self.queue = collections.deque()
        self.up_to_date = False
        self.exit = False
        # Signals that processing of a given event.
        self.process_complete = dict()

        self.event_handlers = {
            z.SERVER_PRESENCE: self.process_server_presence,
            z.SCHEDULED: self.process_scheduled,
            z.EVENTS: self.process_events,
        }

    def _zk_ensure_exists(self, path, acl=None):
        """Ensure ZK node exists, complying with readonly flag."""
        if self.readonly:
            return
        zkutils.ensure_exists(self.zkclient, path, acl=acl)

    def _zk_put(self, path, data, acl=None):
        """Put data in ZK node, complying with readonly flag."""
        if self.readonly:
            return
        zkutils.put(self.zkclient, path, data, acl=acl)

    def _zk_delete(self, path):
        """Ensure ZK node does not exist, complying with readonly flag."""
        if self.readonly:
            return
        zkutils.ensure_deleted(self.zkclient, path)

    def create_rootns(self):
        """Create root nodes and set appropriate acls."""
        if self.readonly:
            return

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
            z.STATE_REPORTS: None,
            z.STRATEGIES: None,
            z.FINISHED: [_SERVERS_ACL],
            z.FINISHED_HISTORY: None,
            z.TRACE: None,
            z.TRACE_HISTORY: None,
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

        for path, acl in six.iteritems(root_ns):
            self._zk_ensure_exists(path, acl)
        for path in z.trace_shards():
            self._zk_ensure_exists(path, [_SERVERS_ACL])

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
        self.cell.partitions[admin.DEFAULT_PARTITION] = scheduler.Partition(
            label=admin.DEFAULT_PARTITION
        )

        partitions = self.zkclient.get_children(z.PARTITIONS)
        for partition in partitions:
            self.load_partition(partition)

    def load_partition(self, partition):
        """Load partition."""
        try:
            _LOGGER.info('loading partition: %s', partition)
            data = zkutils.get(self.zkclient, z.path.partition(partition))
            self.cell.partitions[partition] = scheduler.Partition(
                max_server_uptime=data.get('server_uptime'),
                max_lease=data.get('max_lease'),
                threshold=data.get('threshold'),
                label=partition
            )

        except kazoo.client.NoNodeError:
            _LOGGER.warning('Partition node not found: %s', partition)

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

    def load_servers(self):
        """Load server topology."""
        servers = self.zkclient.get_children(z.SERVERS)
        for servername in servers:
            self.load_server(servername)

    def load_server(self, servername):
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
            label = data.get('partition')
            if not label:
                # TODO: it will be better to have separate module for constants
                #       and avoid unnecessary cross imports.
                label = admin.DEFAULT_PARTITION
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
                _LOGGER.warning('Server parent does not exist: %s/%s',
                                servername, parentname)
                return

            self.buckets[parentname].add_node(server)
            self.servers[servername] = server
            assert server.parent == self.buckets[parentname]

            self._zk_ensure_exists(
                z.path.placement(servername),
                acl=[_SERVERS_ACL]
            )

            self.adjust_server_state(servername)

        except kazoo.client.NoNodeError:
            _LOGGER.warning('Server node not found: %s', servername)

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

            # TODO: seems like this is cut/paste code from load_server.
            label = data.get('partition')
            if not label:
                label = admin.DEFAULT_PARTITION
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
            _LOGGER.warning('Server node not found: %s', servername)

    def adjust_server_state(self, servername):
        """Set server state."""
        server = self.servers.get(servername)
        if not server:
            return

        is_up = self.zkclient.exists(z.path.server_presence(servername))

        placement_node = z.path.placement(servername)

        # Restore state as it was stored in server placement node.
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
        self._zk_put(placement_node, {'state': state.value, 'since': since})

    def load_allocations(self):
        """Load allocations and assignments map."""
        data = zkutils.get_default(self.zkclient, z.ALLOCATIONS, default={})
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
        apps = self.zkclient.get_children(z.SCHEDULED)
        for appname in apps:
            self.load_app(appname)

    def load_app(self, appname):
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

            server = self.servers[servername]
            server.remove_all()

            for appname in placed_apps:
                appnode = z.path.placement(servername, appname)
                if appname not in self.cell.apps:
                    # Stale app - safely ignored.
                    self._zk_delete(appnode)
                    continue

                # Try to restore placement, if failed (e.g capacity of the
                # servername changed - remove.
                #
                # The servername does not need to be active at the time,
                # for applications will be moved from servers in DOWN state
                # on subsequent reschedule.
                app = self.cell.apps[appname]
                integrity[appname].append(servername)

                # Placement is restored and assumed to be correct, so
                # force placement be specifying the server label.
                assert app.allocation is not None
                _LOGGER.info('Restore placement %s => %s', appname, servername)
                if not server.put(app):
                    _LOGGER.info('Failed to restore placement %s => %s',
                                 appname, servername)
                    self._zk_delete(appnode)
                    # Check if app is marked to be scheduled once. If it is
                    # remove the app.
                    if app.schedule_once:
                        _LOGGER.info('Removing scheduled once app: %s',
                                     appname)
                        self.cell.remove_app(appname)
                        self._zk_delete(z.path.scheduled(appname))

        for appname, servers in six.iteritems(integrity):
            if len(servers) <= 1:
                continue

            _LOGGER.warning(
                'Integrity error: %s placed on %r', appname, servers
            )
            for servername in servers:
                self.servers[servername].remove(appname)
                self._zk_delete(z.path.placement(servername, appname))

    def load_placement_data(self):
        """Restore app identities."""
        for appname, app in six.iteritems(self.cell.apps):
            if not app.server:
                continue

            placement_data = zkutils.get_default(
                self.zkclient,
                z.path.placement(app.server, appname)
            )

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
        if self.readonly:
            # Not interested in repairing placements when in readonly mode
            return

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
                    self._zk_delete(z.path.placement(server, app))

                if app2server[app] != correct_placement:
                    _LOGGER.critical('Removing incorrect placement: %s/%s',
                                     app2server[app], app)
                    self._zk_delete(z.path.placement(app2server[app], app))

        # Cross check that all apps in the model are recorded in placement.
        success = True
        for appname, app in six.iteritems(self.cell.apps):
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

    def save_state_reports(self):
        """Prepare scheduler reports and save them to ZooKeeper."""
        if self.readonly:
            # Can't save reports to ZK in readonly mode
            return

        for report_type in ('servers', 'allocations', 'apps'):
            _LOGGER.info('Saving scheduler report "%s" to ZooKeeper',
                         report_type)
            self._zk_put(
                z.path.state_report(report_type),
                getattr(reports, report_type)(self.cell).to_csv()
            )

    @utils.exit_on_unhandled
    def process(self, event):
        """Process state change event."""
        path, children = event
        _LOGGER.info('processing: %r', event)

        assert path in self.event_handlers
        self.event_handlers[path](children)

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
                self._zk_delete(z.path.placement(app.server, appname))
            if self.events_dir:
                appevents.post(
                    self.events_dir,
                    traceevents.DeletedTraceEvent(
                        instanceid=appname
                    )
                )
            # If finished does not exist, it means app is terminated by
            # explicit request, not because it finished on the node.
            if not self.zkclient.exists(z.path.finished(appname)):
                zkutils.with_retry(
                    self._zk_put,
                    z.path.finished(appname),
                    {'state': 'terminated',
                     'when': time.time(),
                     'host': app.server,
                     'data': None},
                    acl=[_SERVERS_ACL],
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
                # Changing allocations has potential of complete
                # reshuffle, so while ineffecient, reload all apps as well.
                #
                # If application is assigned to different partition, from
                # scheduler perspective is no different than host deleted. It
                # will be detected on schedule and app will be assigned new
                # host from proper partition.
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
            elif resource == 'buckets':
                self.load_buckets()
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
                _LOGGER.warning('Unsupported event resource: %s', resource)

        for node in events:
            _LOGGER.info('Deleting event: %s', z.path.event(node))
            self._zk_delete(z.path.event(node))

    def watch(self, path):
        """Constructs a watch on a given path."""

        @self.zkclient.ChildrenWatch(path)
        @utils.exit_on_unhandled
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
                self.process_complete[path] = \
                    self.zkclient.handler.event_object()

            _LOGGER.debug('watcher finished: %s', path)
            return True

    def load_model(self):
        """Load cell state from Zookeeper."""
        self.load_partitions()
        self.load_buckets()
        self.load_cell()
        self.load_servers()
        self.load_allocations()
        self.load_strategies()
        self.load_apps()
        self.restore_placements()
        self.load_identity_groups()
        self.load_placement_data()

    def attach_watchers(self):
        """Attach watchers that push ZK children events into a queue."""
        self.watch(z.SERVER_PRESENCE)
        self.watch(z.SCHEDULED)
        self.watch(z.EVENTS)

    @utils.exit_on_unhandled
    def run_loop(self):
        """Run the master loop."""
        self.create_rootns()
        self.load_model()
        self.init_schedule()
        self.attach_watchers()

        last_sched_time = time.time()
        last_integrity_check = 0
        last_reboot_check = 0
        last_state_report = 0
        while not self.exit:
            # Process ZK children events queue
            queue_empty = False
            for _idx in range(0, EVENT_BATCH_COUNT):
                try:
                    event = self.queue.popleft()
                    self.process(event)
                except IndexError:
                    queue_empty = True
                    break

            # Run periodic tasks

            if time_past(last_sched_time + SCHEDULER_INTERVAL):
                last_sched_time = time.time()
                if not self.up_to_date:
                    self.reschedule()
                    self.check_placement_integrity()

            if time_past(last_state_report + STATE_REPORT_INTERVAL):
                last_state_report = time.time()
                self.save_state_reports()

            if time_past(last_integrity_check + INTEGRITY_INTERVAL):
                assert self.check_integrity()
                last_integrity_check = time.time()

            if time_past(last_reboot_check + REBOOT_CHECK_INTERVAL):
                self.check_reboot()
                last_reboot_check = time.time()

            if queue_empty:
                time.sleep(CHECK_EVENT_INTERVAL)

    @utils.exit_on_unhandled
    def run(self):
        """Runs the master (once it is elected leader)."""
        if self.readonly:
            # Readonly masters don't need election locks
            return self.run_loop()

        lock = zkutils.make_lock(self.zkclient, z.path.election(__name__))
        _LOGGER.info('Waiting for leader lock.')
        with lock:
            self.run_loop()

    def _schedule_reboot(self, servername):
        """Schedule server reboot."""
        self._zk_ensure_exists(
            z.path.reboot(servername),
            acl=[_SERVERS_ACL_DEL]
        )

    def check_reboot(self):
        """Identify all expired servers."""
        self.cell.resolve_reboot_conflicts()

        now = time.time()

        # expired servers rebooted unconditionally, as they are no use anumore.
        for name, server in six.iteritems(self.servers):
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

    def init_schedule(self):
        """Run scheduler first time and update scheduled data."""
        placement = self.cell.schedule()

        for servername, server in six.iteritems(self.cell.members()):
            placement_node = z.path.placement(servername)
            self._zk_ensure_exists(placement_node, acl=[_SERVERS_ACL])

            current = set(self.zkclient.get_children(placement_node))
            correct = set(server.apps.keys())

            for app in current - correct:
                _LOGGER.info('Unscheduling: %s - %s', servername, app)
                self._zk_delete(os.path.join(placement_node, app))
            for app in correct - current:
                _LOGGER.info('Scheduling: %s - %s,%s',
                             servername, app, self.cell.apps[app].identity)

                placement_data = self._placement_data(app)
                self._zk_put(
                    os.path.join(placement_node, app),
                    placement_data,
                    acl=[_SERVERS_ACL]
                )

                self._update_task(app, servername, why=None)

        # Store latest placement as reference.
        self._zk_put(z.path.placement(), placement)
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
        for app, before, _exp_before, after, _exp_after in changed_placement:
            if before and before != after:
                _LOGGER.info('Unscheduling: %s - %s', before, app)
                self._zk_delete(z.path.placement(before, app))

        for app, before, _exp_before, after, exp_after in changed_placement:
            placement_data = self._placement_data(app)

            why = ''
            if before is not None:
                if (before not in self.servers or
                        self.servers[before].state == scheduler.State.down):
                    why = '{server}:down'.format(server=before)
                else:
                    # TODO: it will be nice to put app utilization at the time
                    #       of eviction, but this info is not readily
                    #       available yet in the scheduler.
                    why = 'evicted'

            if after:
                _LOGGER.info('Scheduling: %s - %s,%s, expires at: %s',
                             after,
                             app,
                             self.cell.apps[app].identity,
                             exp_after)

                self._zk_put(
                    z.path.placement(after, app),
                    placement_data,
                    acl=[_SERVERS_ACL]
                )
                self._update_task(app, after, why=why)
            else:
                self._update_task(app, None, why=why)

        self._unschedule_evicted()

        # Store latest placement as reference.
        self._zk_put(z.path.placement(), placement)
        self.up_to_date = True

    def _unschedule_evicted(self):
        """Delete schedule once and evicted apps."""
        # Apps that were evicted and are configured to be scheduled once
        # should be removed.
        #
        # Remove will trigger rescheduling which will be harmless but
        # strictly speaking unnecessary.
        for appname, app in six.iteritems(self.cell.apps):
            if app.schedule_once and app.evicted:
                _LOGGER.info('Removing schedule_once/evicted app: %s',
                             appname)
                # TODO: need to publish trace event.
                self._zk_delete(z.path.scheduled(appname))

    def _update_task(self, appname, server, why):
        """Creates/updates application task with the new placement."""
        # Servers in the cell have full control over task node.
        if self.events_dir:
            if server:
                appevents.post(
                    self.events_dir,
                    traceevents.ScheduledTraceEvent(
                        instanceid=appname,
                        where=server,
                        why=why
                    )
                )
            else:
                appevents.post(
                    self.events_dir,
                    traceevents.PendingTraceEvent(
                        instanceid=appname,
                        why=why
                    )
                )

    def _abort_task(self, appname, exception):
        """Set task into aborted state in case of scheduling error."""
        if self.events_dir:
            appevents.post(
                self.events_dir,
                traceevents.AbortedTraceEvent(
                    instanceid=appname,
                    why=app_abort.SCHEDULER,
                    payload=exception
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


def create_apps(zkclient, app_id, app, count, created_by=None):
    """Schedules new apps."""
    instance_ids = []
    acl = zkutils.make_role_acl('servers', 'rwcda')
    for _idx in range(0, count):
        node_path = zkutils.put(zkclient,
                                _app_node(app_id, existing=False),
                                app,
                                sequence=True,
                                acl=[acl])
        instance_id = os.path.basename(node_path)
        instance_ids.append(instance_id)

        appevents.post_zk(
            zkclient,
            traceevents.PendingTraceEvent(
                instanceid=instance_id,
                why='%s:created' % created_by if created_by else 'created',
                payload=''
            )
        )

    return instance_ids


def delete_apps(zkclient, app_ids, deleted_by=None):
    """Unschedules apps."""
    for app_id in app_ids:
        zkutils.ensure_deleted(zkclient, _app_node(app_id))

        appevents.post_zk(
            zkclient,
            traceevents.PendingDeleteTraceEvent(
                instanceid=app_id,
                why='%s:deleted' % deleted_by if deleted_by else 'deleted'
            )
        )


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
    modified = []
    for app_id, priority in six.iteritems(updates):
        assert 0 <= priority <= 100

        app = get_app(zkclient, app_id)
        if app is None:
            # app does not exist.
            continue

        app['priority'] = priority

        if zkutils.update(zkclient, _app_node(app_id), app,
                          check_content=True):
            modified.append(app_id)

    if modified:
        create_event(zkclient, 1, 'apps', modified)


def create_bucket(zkclient, bucket_id, parent_id, traits=0):
    """Creates bucket definition in Zookeeper."""
    data = {
        'traits': traits,
        'parent': parent_id
    }
    zkutils.put(zkclient, z.path.bucket(bucket_id), data, check_content=True)
    create_event(zkclient, 0, 'buckets', None)


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
    # NOTE: we never remove buckets, no need for event.


def list_buckets(zkclient):
    """List all buckets."""
    return sorted(zkclient.get_children(z.BUCKETS))


def create_server(zkclient, server_id, parent_id):
    """Creates server definition in Zookeeper."""
    server_node = z.path.server(server_id)
    server_acl = zkutils.make_host_acl(server_id, 'rwcd')

    zkutils.ensure_exists(zkclient, server_node, acl=[server_acl])

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


def update_server_attrs(zkclient, server_id, traits, partition):
    """Updates server traits."""
    node = z.path.server(server_id)
    data = zkutils.get(zkclient, node)
    data['traits'] = traits
    data['partition'] = partition

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


def update_server_features(zkclient, server_id, features):
    """Updates server features."""
    node = z.path.server(server_id)
    data = zkutils.get(zkclient, node)
    data['features'] = features

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


def update_allocations(zkclient, allocations):
    """Updates identity group count."""
    if zkutils.put(zkclient,
                   z.path.allocation(),
                   allocations,
                   check_content=True):
        create_event(zkclient, 0, 'allocations', None)
