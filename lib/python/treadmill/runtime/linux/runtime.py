"""Linux runtime interface.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import appcfg
from treadmill import supervisor
from treadmill.runtime import runtime_base

from . import _run as app_run
from . import _finish as app_finish

_LOGGER = logging.getLogger(__name__)


class LinuxRuntime(runtime_base.RuntimeBase):
    """Linux Treadmill runtime."""

    def __init__(self, tm_env, container_dir, param=None):
        super(LinuxRuntime, self).__init__(
            tm_env, container_dir, param
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
        app_run.run(self._tm_env, self._service.data_dir, manifest)

    def _finish(self):
        app_finish.finish(self._tm_env, self._service.directory)

    def kill(self):
        services_dir = os.path.join(self._service.data_dir, 'sys',
                                    'start_container')
        try:
            supervisor.control_service(services_dir,
                                       supervisor.ServiceControlAction.kill)
        except subprocess.CalledProcessError as err:
            if err.returncode in (supervisor.ERR_COMMAND,
                                  supervisor.ERR_NO_SUP):
                # Ignore the error if there is no supervisor
                _LOGGER.info('Cannot control supervisor of %r.',
                             services_dir)
            else:
                raise
