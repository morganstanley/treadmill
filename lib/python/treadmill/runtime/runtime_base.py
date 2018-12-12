"""Base runtime interface.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import logging
import os
import shutil

import six

from treadmill import appcfg
from treadmill import exc
from treadmill import supervisor

from treadmill.appcfg import abort as app_abort
from treadmill.appcfg import manifest as app_manifest

_LOGGER = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class RuntimeBase:
    """Base class for a Treadmill runtime.

    :param tm_env:
        The Treadmill application environment
    :type tm_env:
        `appenv.AppEnvironment`
    :param container_dir:
        Full path to the application container directory
    :type container_dir:
        ``str``
    """
    __slots__ = (
        '_tm_env',
        '_service',
        '_param',
    )

    def __init__(self, tm_env, container_dir, param=None):
        self._tm_env = tm_env
        self._param = {} if param is None else param
        self._service = supervisor.open_service(container_dir)

    @abc.abstractmethod
    def _can_run(self, manifest):
        """Determines if the manifest can run with the runtime.

        :returns:
            ``True`` if can run
        :rtype:
            ``Boolean``
        """

    @abc.abstractmethod
    def _run(self, manifest):
        """Prepares container environment and exec's container.
        """

    def run(self):
        """Prepares container environment and exec's container

        The function is intended to be invoked from 'run' script and never
        returns.

        :returns:
            This function never returns
        """
        manifest_file = os.path.join(self._service.data_dir, appcfg.APP_JSON)
        manifest = app_manifest.read(manifest_file)
        if not self._can_run(manifest):
            raise exc.ContainerSetupError('invalid_type',
                                          app_abort.AbortedReason.INVALID_TYPE)

        self._run(manifest)

    @abc.abstractmethod
    def _finish(self):
        """Frees allocated resources and mark then as available.
        """

    def finish(self):
        """Frees allocated resources and mark then as available.
        """
        # Required because on windows log files are archived and deleted
        # which cannot happen when the supervisor/log is still running.
        supervisor.ensure_not_supervised(self._service.directory)

        self._finish()

        shutil.rmtree(self._service.directory)
        _LOGGER.info('Finished cleanup: %s', self._service.directory)

    @abc.abstractmethod
    def kill(self):
        """Kills a container.
        """

    @classmethod
    def manifest(cls, tm_env, manifest):
        """Add runtime modification to manifest, default does nothing.
        """
