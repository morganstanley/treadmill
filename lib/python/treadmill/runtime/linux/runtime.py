"""Linux runtime interface.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os

from six.moves import configparser

from treadmill import appcfg
from treadmill import exc
from treadmill import subproc
from treadmill import services
from treadmill import supervisor
from treadmill.appcfg import abort as app_abort
from treadmill import utils
from treadmill.runtime import runtime_base

from . import _run as app_run
from . import _finish as app_finish
from . import _manifest as app_manifest

_LOGGER = logging.getLogger(__name__)

#: Runtime config file name.
_RUNTIME_CONFIG = 'runtime.cfg'


class LinuxRuntime(runtime_base.RuntimeBase):
    """Linux Treadmill runtime."""

    name = 'linux'

    __slots__ = (
        '_config',
    )

    def __init__(self, tm_env, container_dir, param=None):
        super(LinuxRuntime, self).__init__(tm_env, container_dir, param)
        self._config = _load_config(
            os.path.join(tm_env.configs_dir, _RUNTIME_CONFIG)
        )

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
        try:
            app_run.run(
                tm_env=self._tm_env,
                runtime_config=self._config,
                container_dir=self._service.data_dir,
                manifest=manifest
            )
        except services.ResourceServiceTimeoutError as err:
            raise exc.ContainerSetupError(
                err.message,
                app_abort.AbortedReason.TIMEOUT
            )

    def _finish(self):
        app_finish.finish(self._tm_env, self._service.directory)

    def kill(self):
        services_dir = os.path.join(self._service.data_dir, 'sys',
                                    'start_container')
        try:
            supervisor.control_service(services_dir,
                                       supervisor.ServiceControlAction.kill)
        except subproc.CalledProcessError as err:
            if err.returncode in (supervisor.ERR_COMMAND,
                                  supervisor.ERR_NO_SUP):
                # Ignore the error if there is no supervisor
                _LOGGER.info('Cannot control supervisor of %r.',
                             services_dir)
            else:
                raise

    @classmethod
    def manifest(cls, tm_env, manifest):
        super(LinuxRuntime, cls).manifest(tm_env, manifest)
        app_manifest.add_runtime(tm_env, manifest)


def _load_config(config_file):
    """Load the linux runtime configuration.
    """
    cp = configparser.SafeConfigParser()
    with io.open(config_file) as f:
        cp.readfp(f)  # pylint: disable=deprecated-method

    conf = {
        'host_mount_whitelist': cp.get(
            'linux', 'host_mount_whitelist', fallback=''
        ).split(',')
    }

    return utils.to_obj(conf)


__all__ = [
    'LinuxRuntime',
]
