"""Implementation of Cgroup API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill.metrics import engine

_LOGGER = logging.getLogger(__name__)


class API:
    """Treadmill Cgroup REST api."""

    def __init__(self, app_root=None, cgroup_prefix=None):

        reader = engine.CgroupReader(app_root, cgroup_prefix)

        def system(path, *paths):
            """Get aggregated system-level cgroup value."""
            return reader.read_system(path, *paths)

        def service(svc):
            """Get treadmill core service cgroup value."""
            return reader.read_service(svc)

        def services(detail=False):
            """Get all treadmill core service cgroup names along with values.
            """
            return reader.read_services(detail=detail)

        def app(name):
            """Get treadmill app cgroup value."""
            return reader.read_app(name)

        def apps(detail=False):
            """Get all treadmill app cgroup names along with values."""
            return reader.read_apps(detail=detail)

        self.system = system
        self.service = service
        self.services = services
        self.app = app
        self.apps = apps
