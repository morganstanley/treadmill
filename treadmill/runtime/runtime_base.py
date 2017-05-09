"""Base runtime interface."""

import abc
import os

import six

from treadmill import exc

from treadmill.appcfg import manifest as app_manifest

_APP_YML = 'app.yml'


@six.add_metaclass(abc.ABCMeta)
class RuntimeBase(object):
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
        'tm_env',
        'container_dir',
        'watchdog'
    )

    def __init__(self, tm_env, container_dir):
        self.tm_env = tm_env
        self.container_dir = container_dir
        self.watchdog = None

    @abc.abstractmethod
    def _can_run(self, manifest):
        """Determines if the manifest can run with the runtime.

        :returns:
            ``True`` if can run
        :rtype:
            ``Boolean``
        """
        pass

    @abc.abstractmethod
    def _run(self, manifest, watchdog, terminated):
        """Prepares container environment and exec's container."""
        pass

    def run(self, terminated):
        """Prepares container environment and exec's container

        The function is intended to be invoked from 'run' script and never
        returns.

        :param terminated:
            Flag where terminated signal will accumulate.
        :param terminated:
            ``set``
        :returns:
            This function never returns
        """
        manifest_file = os.path.join(self.container_dir, _APP_YML)
        manifest = app_manifest.read(manifest_file)
        if not self._can_run(manifest):
            raise exc.ContainerSetupError(
                'Runtime {0} does not support {1}.'.format(
                    self.__class__.__name__,
                    manifest.get('type')
                )
            )

        watchdog_name = 'app_run-%s' % os.path.basename(self.container_dir)
        self.watchdog = self.tm_env.watchdogs.create(
            watchdog_name, '60s',
            'Run of {0} stalled'.format(self.container_dir))

        self._run(manifest, self.watchdog, terminated)

    @abc.abstractmethod
    def _finish(self):
        """Frees allocated resources and mark then as available."""
        pass

    def finish(self):
        """Frees allocated resources and mark then as available."""
        self._finish()

    @abc.abstractmethod
    def _register(self, manifest, refresh_interval=None):
        """Register/Start container presence."""
        pass

    def register(self, manifest_file, refresh_interval=None):
        """Register/Start container presence."""
        manifest = app_manifest.read(manifest_file)
        self._register(manifest, refresh_interval)

    @abc.abstractmethod
    def _monitor(self, manifest):
        """Monitor container services."""
        pass

    def monitor(self, manifest_file):
        """Monitor container services."""
        manifest = app_manifest.read(manifest_file)
        self._monitor(manifest)

    def __del__(self):
        if self.watchdog is not None:
            self.watchdog.remove()
