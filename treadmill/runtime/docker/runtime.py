"""Docker runtime interface.
"""

from treadmill import appcfg

from treadmill.runtime import runtime_base


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
        raise Exception("Not implemented.")

    def _finish(self, watchdog, terminated):
        # TODO: Docker
        raise Exception("Not implemented.")

    def _register(self, manifest, refresh_interval=None):
        # TODO: Docker
        raise Exception("Not implemented.")

    def _monitor(self, manifest):
        # TODO: Docker
        raise Exception("Not implemented.")
