"""Manages Treadmill applications lifecycle."""


# Pylint warning re string being deprecated
#
# pylint: disable=W0402

import logging
import os
import string

from .. import fs
from .. import rulefile
from .. import services
from .. import utils
from .. import watchdog

if os.name == 'nt':
    import socket
else:
    import netifaces


_LOGGER = logging.getLogger(__name__)


class AppEnvironment(object):
    """Treadmill application environment.

    :param root:
        Path to the root directory of the Treadmill environment
    :type root:
        `str`
    """

    __slots__ = (
        'apps_dir',
        'archives_dir',
        'cache_dir',
        'cleanup_dir',
        'init_dir',
        'host_if',
        'host_ip',
        'metrics_dir',
        'pending_cleanup_dir',
        'root',
        'rules',
        'rules_dir',
        'running_dir',
        'svc_cgroup',
        'svc_cgroup_dir',
        'svc_localdisk',
        'svc_localdisk_dir',
        'svc_network',
        'svc_network_dir',
        'app_events_dir',
        'watchdogs',
        'watchdog_dir',
    )

    APPS_DIR = 'apps'
    ARCHIVES_DIR = 'archives'
    CACHE_DIR = 'cache'
    CLEANUP_DIR = 'cleanup'
    INIT_DIR = 'init'
    PENDING_CLEANUP_DIR = 'pending_cleanup'
    RULES_DIR = 'rules'
    RUNNING_DIR = 'running'
    METRICS_DIR = 'metrics'
    WATCHDOG_DIR = 'watchdogs'
    APP_EVENTS_DIR = 'appevents'

    SVC_CGROUP_DIR = 'cgroup_svc'
    SVC_LOCALDISK_DIR = 'localdisk_svc'
    SVC_NETWORK_DIR = 'network_svc'

    def __init__(self, root):
        self.root = root

        self.apps_dir = os.path.join(self.root, self.APPS_DIR)
        self.watchdog_dir = os.path.join(self.root, self.WATCHDOG_DIR)
        self.running_dir = os.path.join(self.root, self.RUNNING_DIR)
        self.cache_dir = os.path.join(self.root, self.CACHE_DIR)
        self.cleanup_dir = os.path.join(self.root, self.CLEANUP_DIR)
        self.app_events_dir = os.path.join(self.root, self.APP_EVENTS_DIR)
        self.metrics_dir = os.path.join(self.root, self.METRICS_DIR)
        self.archives_dir = os.path.join(self.root, self.ARCHIVES_DIR)
        self.rules_dir = os.path.join(self.root, self.RULES_DIR)
        self.init_dir = os.path.join(self.root, self.INIT_DIR)
        self.pending_cleanup_dir = os.path.join(self.root,
                                                self.PENDING_CLEANUP_DIR)

        fs.mkdir_safe(self.apps_dir)
        fs.mkdir_safe(self.watchdog_dir)
        fs.mkdir_safe(self.running_dir)
        fs.mkdir_safe(self.cache_dir)
        fs.mkdir_safe(self.cleanup_dir)
        fs.mkdir_safe(self.app_events_dir)
        fs.mkdir_safe(self.metrics_dir)
        fs.mkdir_safe(self.archives_dir)
        fs.mkdir_safe(self.rules_dir)

        if os.name == 'posix':
            self.svc_cgroup_dir = os.path.join(self.root, self.SVC_CGROUP_DIR)
            self.svc_localdisk_dir = os.path.join(self.root,
                                                  self.SVC_LOCALDISK_DIR)
            self.svc_network_dir = os.path.join(self.root,
                                                self.SVC_NETWORK_DIR)

            # Make sure our directories exists.
            fs.mkdir_safe(self.svc_cgroup_dir)
            fs.mkdir_safe(self.svc_localdisk_dir)
            fs.mkdir_safe(self.svc_network_dir)

            self.rules = rulefile.RuleMgr(self.rules_dir, self.apps_dir)
            # Services
            self.svc_cgroup = services.ResourceService(
                service_dir=self.svc_cgroup_dir,
                impl=('treadmill.services.cgroup_service.'
                      'CgroupResourceService'),
            )
            self.svc_localdisk = services.ResourceService(
                service_dir=self.svc_localdisk_dir,
                impl=('treadmill.services.cgroup_service.'
                      'LocalDiskResourceService'),
            )

            self.svc_network = services.ResourceService(
                service_dir=self.svc_network_dir,
                impl=('treadmill.services.cgroup_service.'
                      'NetworkResourceService'),
            )

        self.host_ip = self._get_host_ip_address()

        self.watchdogs = watchdog.Watchdog(self.watchdog_dir)

    def _get_host_ip_address(self):
        if os.name == 'nt':
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        else:
            ifaddresses = netifaces.ifaddresses('eth0')
            # XXX: (boysson) We are taking the first IPv4 assigned to
            # the host_if.
            return ifaddresses[netifaces.AF_INET][0]['addr']


def gen_uniqueid(event_file):
    """Generate a uniqueid for a given event file

    Uniqueid needs to be length constrained (exactly 13 char) and character set
    constrained ([a-z0-9]) to avoid issues with the naming limitations of the
    different resources of the container (root dir, logical volume, virtual
    ethernet device, ...)

    The current smallest length limiter is:

        virtual ethernet device(13): IFNAMESZ 16 char
                                     - 1 (zero terminated)
                                     - 2 ('.0'/'.1' suffix)

    This function will output an unique identifier of a maximum of 13 chars
    by encoding the event's instance_id, inode number and ctime in base 62.

    :param event_file:
        Full path to an event file
    :type event_file:
        ``str``
    :returns:
        (``str``) -- 13 chars identifier
    """

    event_stat = os.stat(event_file)
    # Event time is the creation time in millisec
    event_time = int(event_stat.st_ctime * 10**6)

    # Event data is the event inode (64bit) combined with the instance id
    # (33bit)
    # Why: InstanceID is 10 digits:
    #      int(10 * math.log(10) / math.log(2)) -> 33
    event_data = int(event_stat.st_ino)
    _name, _sep, instance = os.path.basename(event_file).rpartition('#')
    event_data ^= (int(instance) << 31)
    event_data &= (2 ** 64) - 1

    seed = (event_time << 64) + int(event_data)

    # Trim the top bits so that we only consider 77bits.
    # Note we trim from the ctime high bits.
    # Why: int(13 * math.log(62) / math.log(2)) -> 77
    seed &= (2 ** 77) - 1

    numerals = string.digits + string.ascii_lowercase + string.ascii_uppercase
    ret = utils.to_base_n(seed, base=len(numerals), alphabet=numerals)

    return '{identifier:>013s}'.format(identifier=ret)


def _fmt_unique_name(app_name, app_uniqueid):
    """Format app data into a unique app name.
    """
    return "{app}-{id:>013s}".format(
        app=app_name.replace('#', '-'),
        id=app_uniqueid,
    )


def app_unique_name(app):
    """Unique app name for a given app object.
    """
    return _fmt_unique_name(app.name, app.uniqueid)


def manifest_unique_name(manifest):
    """Unique app name for a given app manifest dictionary.
    """
    return _fmt_unique_name(manifest['name'], manifest['uniqueid'])


def eventfile_unique_name(eventfile):
    """Unique app name for a given event file object.
    """
    uniqueid = gen_uniqueid(eventfile)
    name = os.path.basename(eventfile)
    return _fmt_unique_name(name, uniqueid)


def appname_task_id(appname):
    """Returns the task id from app instance name."""
    _appname, taskid = appname.split('#')
    return taskid


def appname_basename(appname):
    """Returns the base name of the app instance without instance id."""
    basename, _taskid = appname.split('#')
    return basename
