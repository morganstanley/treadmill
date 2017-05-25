"""Base runtime interface."""

from __future__ import absolute_import

import abc
import os

import six

from treadmill import appcfg
from treadmill import exc
from treadmill import utils

from treadmill.appcfg import manifest as app_manifest


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

    def run_timeout(self, _manifest):
        """The run watchdog timeout.

        :param manifest:
            The application manifest.
        :type manifest:
            ``dict``
        :returns:
            The timeout as a string
        :rtype:
            ``str``
        """
        return '60s'

    @abc.abstractmethod
    def _run(self, manifest, watchdog, terminated):
        """Prepares container environment and exec's container."""
        pass

    def run(self):
        """Prepares container environment and exec's container

        The function is intended to be invoked from 'run' script and never
        returns.

        :returns:
            This function never returns
        """
        manifest_file = os.path.join(self.container_dir, appcfg.APP_JSON)
        manifest = app_manifest.read(manifest_file)
        if not self._can_run(manifest):
            raise exc.ContainerSetupError(
                'Runtime {0} does not support {1}.'.format(
                    self.__class__.__name__,
                    manifest.get('type')
                )
            )

        # Intercept SIGTERM from supervisor, so that initialization is not
        # left in broken state.
        terminated = utils.make_signal_flag(utils.term_signal())

        unique_name = appcfg.manifest_unique_name(manifest)
        watchdog_name = 'app_run-%s' % unique_name
        self.watchdog = self.tm_env.watchdogs.create(
            watchdog_name, self.run_timeout(manifest),
            'Run of {container_dir!r} stalled'.format(
                container_dir=self.container_dir
            )
        )

        self._run(manifest, self.watchdog, terminated)

    @property
    def finish_timeout(self):
        """The finish watchdog timeout.

        :returns:
            The timeout as a string
        :rtype:
            ``str``
        """
        # FIXME: The watchdog value below is inflated to account for
        #        the extra archiving time.
        return '5m'

    @abc.abstractmethod
    def _finish(self, watchdog, terminated):
        """Frees allocated resources and mark then as available."""
        pass

    def finish(self):
        """Frees allocated resources and mark then as available."""

        # Intercept SIGTERM from supervisor, so that finish is not
        # left in broken state.
        terminated = utils.make_signal_flag(utils.term_signal())

        # FIXME(boysson): The watchdog value below is inflated to account for
        #                 the extra archiving time.
        watchdog_name = 'app_finish-%s' % os.path.basename(self.container_dir)
        self.watchdog = self.tm_env.watchdogs.create(
            watchdog_name, self.finish_timeout,
            'Cleanup of {0} stalled'.format(self.container_dir)
        )

        self._finish(self.watchdog, terminated)

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
