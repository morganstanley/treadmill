"""Linux application environment.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

from treadmill import apphook
from treadmill import fs
from treadmill import iptables
from treadmill import rulefile
from treadmill import services
from treadmill.runtime.linux.image import fs as image_fs

from . import appenv

_LOGGER = logging.getLogger(__name__)


class LinuxAppEnvironment(appenv.AppEnvironment):
    """Linux Treadmill application environment.

    :param root:
        Path to the root directory of the Treadmill environment
    :type root:
        `str`
    """

    __slots__ = (
        'metrics_dir',
        'spool_dir',
        'svc_cgroup',
        'svc_cgroup_dir',
        'svc_localdisk',
        'svc_localdisk_dir',
        'svc_network',
        'svc_network_dir',
        'rules',
        'rules_dir'
    )

    METRICS_DIR = 'metrics'
    SPOOL_DIR = 'spool'
    SVC_CGROUP_DIR = 'cgroup_svc'
    SVC_LOCALDISK_DIR = 'localdisk_svc'
    SVC_NETWORK_DIR = 'network_svc'
    RULES_DIR = 'rules'

    def __init__(self, root):

        super(LinuxAppEnvironment, self).__init__(root)

        self.metrics_dir = os.path.join(self.root, self.METRICS_DIR)
        self.spool_dir = os.path.join(self.root, self.SPOOL_DIR)
        self.svc_cgroup_dir = os.path.join(self.root, self.SVC_CGROUP_DIR)
        self.svc_localdisk_dir = os.path.join(self.root,
                                              self.SVC_LOCALDISK_DIR)
        self.svc_network_dir = os.path.join(self.root,
                                            self.SVC_NETWORK_DIR)
        self.rules_dir = os.path.join(self.root, self.RULES_DIR)

        # Make sure our directories exists.
        fs.mkdir_safe(self.metrics_dir)
        fs.mkdir_safe(self.spool_dir)
        fs.mkdir_safe(self.svc_cgroup_dir)
        fs.mkdir_safe(self.svc_localdisk_dir)
        fs.mkdir_safe(self.svc_network_dir)
        fs.mkdir_safe(self.rules_dir)

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

    def initialize(self, params):
        """One time initialization of the Treadmill environment."""
        _LOGGER.info('Initializing once.')

        # Flush all rules in iptables nat and mangle tables (it is assumed that
        # none but Treadmill manages these tables) and bulk load all the
        # Treadmill static rules
        iptables.initialize(params['network']['external_ip'])

        # Initialize network rules
        self.rules.initialize()

        # Initialize FS plugins.
        image_fs.init_plugins(self)

        # Initialize container plugin hooks
        apphook.init(self)
