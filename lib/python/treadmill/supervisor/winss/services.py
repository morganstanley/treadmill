"""winss services management.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import os

import six

from treadmill import fs

from .. import _service_base
from .. import _utils


class LongrunService(_service_base.Service):
    """winss long running service.
    """

    __slots__ = (
        '_default_down',
        '_finish_script',
        '_log_run_script',
        '_run_script',
        '_timeout_finish',
        '_env',
    )

    _TYPE = _service_base.ServiceType.LongRun

    def __init__(self, directory, name,
                 run_script=None, finish_script=None, log_run_script=None,
                 timeout_finish=None, default_down=None, environ=None):
        super(LongrunService, self).__init__(
            directory,
            name
        )

        self._default_down = default_down
        self._finish_script = finish_script
        self._log_run_script = log_run_script
        self._run_script = run_script
        self._timeout_finish = timeout_finish
        self._env = environ

    @property
    def type(self):
        return self._TYPE

    @property
    def data_dir(self):
        """Returns the data directory for the services.

        :returns ``str``:
            Full path to the service data directory.
        """
        return os.path.join(self._dir, 'data')

    @property
    def env_dir(self):
        """Returns the environ directory for the services.

        :returns ``str``:
            Full path to the service environ directory.
        """
        return os.path.join(self._dir, 'env')

    @property
    def logger_dir(self):
        """Returns the logger directory for the services.

        :returns ``str``:
            Full path to the service log directory.
        """
        return os.path.join(self._dir, 'log')

    @property
    def default_down(self):
        """Is the default service state set to down?
        """
        if self._default_down is None:
            self._default_down = os.path.exists(
                os.path.join(self._dir, 'down')
            )
        return self._default_down

    @default_down.setter
    def default_down(self, default_down):
        self._default_down = bool(default_down)

    @property
    def _run_file(self):
        return os.path.join(self._dir, 'run')

    @property
    def _finish_file(self):
        return os.path.join(self._dir, 'finish')

    @property
    def _log_run_file(self):
        return os.path.join(self.logger_dir, 'run')

    @property
    def run_script(self):
        """Service run script.
        """
        if self._run_script is None:
            self._run_script = _utils.script_read(self._run_file)
        return self._run_script

    @run_script.setter
    def run_script(self, new_script):
        self._run_script = new_script

    @property
    def finish_script(self):
        """Service finish script.
        """
        if self._finish_script is None:
            try:
                self._finish_script = _utils.script_read(self._finish_file)
            except IOError as err:
                if err.errno is not errno.ENOENT:
                    raise
        return self._finish_script

    @finish_script.setter
    def finish_script(self, new_script):
        self._finish_script = new_script

    @property
    def log_run_script(self):
        """Service log run script.
        """
        if self._log_run_script is None:
            try:
                self._log_run_script = _utils.script_read(self._log_run_file)
            except IOError as err:
                if err.errno is not errno.ENOENT:
                    raise
        return self._log_run_script

    @log_run_script.setter
    def log_run_script(self, new_script):
        self._log_run_script = new_script

    @property
    def timeout_finish(self):
        """Returns amount of milliseconds to wait for the finish script to
        complete.

        :returns ``int``:
            Amount of milliseconds to wait. 0 means infinitely. Default 5000.
        """
        if self._timeout_finish is None:
            self._timeout_finish = _utils.value_read(
                os.path.join(self._dir, 'timeout-finish'),
                default=5000
            )
        return self._timeout_finish

    @timeout_finish.setter
    def timeout_finish(self, timeout_finish):
        """Service finish script timeout.
        """
        if timeout_finish is not None:
            if isinstance(timeout_finish, six.integer_types):
                self._timeout_finish = timeout_finish
            else:
                self._timeout_finish = int(timeout_finish, 10)

    @property
    def environ(self):
        """Returns the environ dictionary for the services.

        :returns ``dict``:
            Service environ dictionary.
        """
        if self._env is None:
            self._env = _utils.environ_dir_read(self.env_dir)
        return self._env

    @environ.setter
    def environ(self, new_environ):
        self._env = new_environ

    def write(self):
        super(LongrunService, self).write()

        fs.mkdir_safe(self.env_dir)
        fs.mkdir_safe(self.data_dir)
        if self._env is not None:
            _utils.environ_dir_write(self.env_dir, self._env)
        if self._run_script is None and not os.path.exists(self._run_file):
            raise ValueError('Invalid LongRun service: not run script')
        elif self._run_script is not None:
            _utils.script_write(self._run_file, self._run_script)
            # Handle the case where the run script is a generator
            if not isinstance(self._run_script, six.string_types):
                self._run_script = None
        # Optional settings
        if self._finish_script is not None:
            _utils.script_write(self._finish_file, self._finish_script)
            # Handle the case where the finish script is a generator
            if not isinstance(self._finish_script, six.string_types):
                self._finish_script = None
        if self._log_run_script is not None:
            # Create the log dir on the spot
            fs.mkdir_safe(os.path.dirname(self._log_run_file))
            _utils.script_write(self._log_run_file, self._log_run_script)
            # Handle the case where the run script is a generator
            if not isinstance(self._log_run_script, six.string_types):
                self._log_run_script = None
        if self._default_down:
            _utils.data_write(
                os.path.join(self._dir, 'down'),
                None
            )
        else:
            fs.rm_safe(os.path.join(self._dir, 'down'))
        if self._timeout_finish is not None:
            _utils.value_write(
                os.path.join(self._dir, 'timeout-finish'),
                self._timeout_finish
            )


# Disable W0613: Unused argument 'svc_type'
# pylint: disable=W0613
def create_service(svc_basedir, svc_name, svc_type, **kwargs):
    """Factory function instantiating a new service object from parameters.

    :param ``str`` svc_basedir:
        Base directory where to create the service.
    :param ``str`` svc_name:
        Name of the new service.
    :param ``supervisor.ServiceType`` _svc_type:
        Type for the new service.
    :param ``dict`` kw_args:
        Additional argument passed to the constructor of the new service.
    :returns ``Service``:
        New instance of the service
    """
    return LongrunService(svc_basedir, svc_name, **kwargs)


__all__ = (
    'LongrunService',
    'create_service',
)
