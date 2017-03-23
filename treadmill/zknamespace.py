"""Treadmill constants."""


import collections
import functools


ALLOCATIONS = '/allocations'
APPGROUPS = '/app-groups'
APPMONITORS = '/app-monitors'
ARCHIVE_CONFIG = '/archive/config'
BLACKEDOUT_APPS = '/blackedout.apps'
BLACKEDOUT_SERVERS = '/blackedout.servers'
BUCKETS = '/buckets'
CELL = '/cell'
ENDPOINTS = '/endpoints'
EVENTS = '/events'
IDENTITY_GROUPS = '/identity-groups'
PLACEMENT = '/placement'
RUNNING = '/running'
SCHEDULED = '/scheduled'
SCHEDULER = '/scheduler'
SERVERS = '/servers'
PARTITIONS = '/partitions'
REBOOTS = '/reboots'
SERVER_PRESENCE = '/server.presence'
STRATEGIES = '/strategies'
TASKS = '/tasks'
TICKET_LOCKER = '/ticket-locker'
TREADMILL = '/treadmill'
VERSION = '/version'
VERSION_ID = '/version-id'
ZOOKEEPER = '/zookeeper'


def join_zookeeper_path(root, *child):
    """"Returns zookeeper path joined by slash."""
    return '/'.join((root,) + child)


def _make_path_f(zkpath):
    """"Return closure that will construct node path."""
    return staticmethod(functools.partial(join_zookeeper_path, zkpath))


@staticmethod
def _path_task(instancename, *components):
    """Returns path of a task object for given app instance."""
    return '/'.join([TASKS] + instancename.split('#') + list(components))


@staticmethod
def _path_endpoint(name, proto, endpoint):
    """Returns path to Zk app endpoint node by name.

    The name is assumed to be <proid>.<xxx> which will result in the path:
    /endpoints/<proid>/<xxx>:<proto>:<endpoint>
    """
    prefix, _sep, rest = name.partition('.')
    return '/'.join(
        [ENDPOINTS, prefix, ':'.join([rest, proto, str(endpoint)])]
    )


@staticmethod
def _path_endpoint_proid(name):
    """Returns path to Zk app endpoint proid node path by name.

    The name is assumed to be <proid>.<xxx> which will result in the path:
    /endpoints/<proid>
    """
    proid, _sep, _rest = name.partition('.')
    return '/'.join([ENDPOINTS, proid])


# pylint: disable=C0103
path = collections.namedtuple('path', """
    allocation
    blackedout_server
    bucket
    cell
    chroot
    event
    placement
    running
    scheduled
    scheduler
    server_presence
    server
    strategy
    ticket_locker
    version
    version_id
    zookeeper
    endpoint
    task
    """)

path.allocation = _make_path_f(ALLOCATIONS)
path.appgroup = _make_path_f(APPGROUPS)
path.appmonitor = _make_path_f(APPMONITORS)
path.blackedout_app = _make_path_f(BLACKEDOUT_APPS)
path.blackedout_server = _make_path_f(BLACKEDOUT_SERVERS)
path.bucket = _make_path_f(BUCKETS)
path.cell = _make_path_f(CELL)
path.chroot = _make_path_f(TREADMILL)
path.event = _make_path_f(EVENTS)
path.identity_group = _make_path_f(IDENTITY_GROUPS)
path.partition = _make_path_f(PARTITIONS)
path.placement = _make_path_f(PLACEMENT)
path.reboot = _make_path_f(REBOOTS)
path.running = _make_path_f(RUNNING)
path.scheduled = _make_path_f(SCHEDULED)
path.scheduler = _make_path_f(SCHEDULER)
path.server_presence = _make_path_f(SERVER_PRESENCE)
path.server = _make_path_f(SERVERS)
path.strategy = _make_path_f(STRATEGIES)
path.ticket_locker = _make_path_f(TICKET_LOCKER)
path.version = _make_path_f(VERSION)
path.version_id = _make_path_f(VERSION_ID)
path.zookeeper = _make_path_f(ZOOKEEPER)

# Special methods
path.endpoint = _path_endpoint
path.endpoint_proid = _path_endpoint_proid
path.task = _path_task
