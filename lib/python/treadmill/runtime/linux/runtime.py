"""Linux runtime interface."""

from __future__ import absolute_import

import logging

from treadmill import appcfg
from treadmill import context

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

    def run_timeout(self, manifest):
        if appcfg.AppType(manifest['type']) is appcfg.AppType.NATIVE:
            return '60s'

        # Inflated to allow time to download and extract the image.
        return '5m'

    def _run(self, manifest, watchdog, terminated):
        app_run.run(self.tm_env, self.container_dir, manifest, watchdog,
                    terminated)

    def _finish(self, watchdog, terminated):
        app_finish.finish(self.tm_env, context.GLOBAL.zk.conn,
                          self.container_dir, watchdog)
