"""Docker runtime interface."""

from __future__ import absolute_import

import logging
import time

from treadmill import appcfg

from treadmill.runtime import runtime_base


_LOGGER = logging.getLogger(__name__)


class DockerRuntime(runtime_base.RuntimeBase):
    """Docker Treadmill runtime."""

    def __init__(self, tm_env, container_dir):
        super(DockerRuntime, self).__init__(tm_env, container_dir)

    def _can_run(self, manifest):
        try:
            return appcfg.AppType(manifest['type']) is appcfg.AppType.DOCKER
        except ValueError:
            return False

    def _run(self, manifest, watchdog, terminated):
        # TODO: Docker
        _LOGGER.info("starting %r", manifest)
        time.sleep(60)

    def _finish(self, watchdog, terminated):
        # TODO: Docker
        _LOGGER.info("finished")
