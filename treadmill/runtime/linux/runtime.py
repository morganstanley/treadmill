"""Linux runtime interface.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import appcfg
from treadmill.runtime import runtime_base

from . import _run as app_run
from . import _finish as app_finish

_LOGGER = logging.getLogger(__name__)


class LinuxRuntime(runtime_base.RuntimeBase):
    """Linux Treadmill runtime."""

    def __init__(self, tm_env, container_dir):
        super(LinuxRuntime, self).__init__(tm_env, container_dir)

    def _can_run(self, manifest):
        try:
            return appcfg.AppType(manifest['type']) in (
                appcfg.AppType.NATIVE,
                appcfg.AppType.TAR
                # TODO: Add support for DOCKER
            )
        except ValueError:
            return False

    def _run(self, manifest):
        app_run.run(self.tm_env, self.container_dir, manifest)

    def _finish(self):
        app_finish.finish(self.tm_env, self.container_dir)
