"""Linux application environment.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

from treadmill import apphook
from treadmill import endpoints
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
        'ctl_dir',
        'endpoints',
        'metrics_dir',
        'mounts_dir',
        'rules',
        'rules_dir',
        'services_tombstone_dir',
        'spool_dir',
        'svc_cgroup',
        'svc_cgroup_dir',
        'svc_localdisk',
        'svc_localdisk_dir',
        'svc_network',
        'svc_network_dir',
        'svc_presence',
        'svc_presence_dir',
    )

    CTL_DIR = 'ctl'
    METRICS_DIR = 'metrics'
    MOUNTS_DIR = 'mnt'
    RULES_DIR = 'rules'
    SERVICES_DIR = 'services'
    SPOOL_DIR = 'spool'
    SVC_CGROUP_DIR = 'cgroup_svc'
    SVC_LOCALDISK_DIR = 'localdisk_svc'
    SVC_NETWORK_DIR = 'network_svc'
    SVC_PRESENCE_DIR = 'presence_svc'
    RULES_DIR = 'rules'
    CTL_DIR = 'ctl'
    SERVICES_DIR = 'services'

    def __init__(self, root):

        super(LinuxAppEnvironment, self).__init__(root)

        self.ctl_dir = os.path.join(self.root, self.CTL_DIR)
        self.metrics_dir = os.path.join(self.root, self.METRICS_DIR)
        self.mounts_dir = os.path.join(self.root, self.MOUNTS_DIR)
        self.rules_dir = os.path.join(self.root, self.RULES_DIR)
        self.services_tombstone_dir = os.path.join(self.tombstones_dir,
                                                   self.SERVICES_DIR)
        self.spool_dir = os.path.join(self.root, self.SPOOL_DIR)
        self.svc_cgroup_dir = os.path.join(self.root, self.SVC_CGROUP_DIR)
        self.svc_localdisk_dir = os.path.join(self.root,
                                              self.SVC_LOCALDISK_DIR)
        self.svc_network_dir = os.path.join(self.root,
                                            self.SVC_NETWORK_DIR)
        self.svc_presence_dir = os.path.join(self.root,
                                             self.SVC_PRESENCE_DIR)

        self.rules = rulefile.RuleMgr(self.rules_dir, self.apps_dir)
        self.endpoints = endpoints.EndpointsMgr(self.endpoints_dir)

        # Services
        self.svc_cgroup = services.ResourceService(
            service_dir=self.svc_cgroup_dir,
            impl='cgroup'
        )
        self.svc_localdisk = services.ResourceService(
            service_dir=self.svc_localdisk_dir,
            impl='localdisk'
        )
        self.svc_network = services.ResourceService(
            service_dir=self.svc_network_dir,
            impl='network'
        )
        self.svc_presence = services.ResourceService(
            service_dir=self.svc_presence_dir,
            impl='presence'
        )

    def initialize(self, params):
        """One time initialization of the Treadmill environment."""
        _LOGGER.info('Initializing once.')

        # TODO: Network initialization. Right now it requires data from the
        # network_svc which isne't running yet.
        # iptables.initialize()

        # Initialize network rules
        self.rules.initialize()

        # Initialize endpoints manager
        self.endpoints.initialize()

        # Initialize FS plugins.
        image_fs.init_plugins(self)

        # Initialize container plugin hooks
        apphook.init(self)
