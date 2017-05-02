"""S6 services management.
"""

from __future__ import absolute_import

import abc
import errno
import logging
import os
import sys

import enum

from treadmill import fs
from ._utils import (
    data_read,
    data_write,
    environ_dir_read,
    environ_dir_write,
    script_read,
    script_write,
    set_list_read,
    set_list_write,
    value_read,
    value_write,
)

_LOGGER = logging.getLogger(__name__)


class ServiceType(enum.Enum):
    """Types of s6 services (per s6-rc definitions).
    """
    LongRun = b'longrun'


class Service(object):
    """Abstract base class / factory of all s6 services.
    """
    __slots__ = (
        '_dir',
        '_name',
    )

    __metaclass__ = abc.ABCMeta

    def __init__(self, directory, name):
        self._name = name
        self._dir = os.path.join(directory, name)

    def __repr__(self):
        return '{type}({name})'.format(
            type=self.__class__.__name__,
            name=self._name,
        )

    @abc.abstractproperty
    def type(self):
        """Type of the service.

        :returns ``ServiceType``:
            Type of the service.
        """
        pass

    @property
    def name(self):
        """Name of the service.

        :returns ``str``:
            Name of the service.
        """
        return self._name

    @property
    def directory(self):
        """Base filesystem directory of the service.

        :returns ``str``:
            Base directory of the service.
        """
        return self._dir

    @abc.abstractmethod
    def write(self):
        """Write down the service definition.
        """
        fs.mkdir_safe(self._dir)
        data_write(os.path.join(self._dir, 'type'), self.type.value)

    @classmethod
    def new(cls, svc_basedir, svc_name, svc_type, **kw_args):
        """Factory function instantiating a new service object from parameters.

        :param ``str`` svc_basedir:
            Base directory where to create the service.
        :param ``str`` svc_name:
            Name of the new service.
        :param ``ServiceType`` svc_type:
            Type for the new service.
        :param ``dict`` kw_args:
            Additional argument passed to the constructor of the new service.
        :returns ``Service``:
            New instance of the service
        """
        svc_mod = sys.modules[cls.__module__]
        svc_type = ServiceType(svc_type)
        svc_cls = getattr(svc_mod, svc_type.name.capitalize() + cls.__name__)
        if svc_cls is None:
            _LOGGER.critical('No implementation for service type %r', svc_type)
            svc_cls = cls

        _LOGGER.debug('Instantiating %r', svc_cls)
        return svc_cls(directory=svc_basedir,
                       name=svc_name,
                       **kw_args)

    @classmethod
    def from_dir(cls, directory):
        """Factory function instantiating a new service object from an existing
        directory.

        :param ``str`` directory:
            Directory where to read the service definition from.
        :returns ``Service``:
            New service instance or ``None`` if parsing failed.
        """
        try:
            svc_type = data_read(os.path.join(directory, 'type'))
        except IOError as err:
            if err.errno is errno.ENOENT:
                return None
            raise
        svc_basedir = os.path.dirname(directory)
        svc_name = os.path.basename(directory)
        return cls.new(svc_basedir=svc_basedir,
                       svc_name=svc_name,
                       svc_type=svc_type)


class _AtomicService(Service):
    """Abstract base class for all atomic services (per s6-rc definition).
    """
    __slots__ = (
        '_dependencies',
        '_timeout_up',
        '_timeout_down',
        '_env',
    )

    __metaclass__ = abc.ABCMeta

    def __init__(self, directory, name,
                 timeout_up=None, timeout_down=None,
                 dependencies=None, environ=None):
        super(_AtomicService, self).__init__(directory, name)
        self._dependencies = dependencies
        self._timeout_up = timeout_up
        self._timeout_down = timeout_down
        self._env = environ

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
    def environ(self):
        """Returns the environ dictionary for the services.

        :returns ``dict``:
            Service environ dictionary.
        """
        if self._env is None:
            self._env = environ_dir_read(self.env_dir)
        return self._env

    @environ.setter
    def environ(self, new_environ):
        self._env = new_environ

    @property
    def _dependencies_file(self):
        return os.path.join(self._dir, 'dependencies')

    @property
    def dependencies(self):
        """Returns the dependencies set for the services.

        :returns ``set``:
            Service dependencies set.
        """
        if self._dependencies is None:
            self._dependencies = set_list_read(self._dependencies_file)
        return self._dependencies

    @dependencies.setter
    def dependencies(self, new_deps):
        self._dependencies = set(new_deps)

    @property
    def timeout_up(self):
        """Returns amount of milliseconds to wait for the service to come up.

        :returns ``int``:
            Amount of milliseconds to wait. 0 means infinitely.
        """
        if self._timeout_up is None:
            self._timeout_up = value_read(
                os.path.join(self._dir, 'timeout-up'),
                default=0
            )
        return self._timeout_up

    @property
    def timeout_down(self):
        """Returns amount of milliseconds to wait for the service to come down.

        :returns ``int``:
            Amount of milliseconds to wait. 0 means infinitely.
        """
        if self._timeout_down is None:
            self._timeout_down = value_read(
                os.path.join(self._dir, 'timeout-down'),
                default=0
            )
        return self._timeout_down

    @abc.abstractmethod
    def write(self):
        """Write down the service definition.
        """
        super(_AtomicService, self).write()
        # We only write dependencies/environ if we have new ones.
        fs.mkdir_safe(self.env_dir)
        fs.mkdir_safe(self.data_dir)
        if self._dependencies is not None:
            set_list_write(self._dependencies_file, self._dependencies)
        if self._env is not None:
            environ_dir_write(self.env_dir, self._env)
        if self._timeout_up is not None:
            value_write(
                os.path.join(self._dir, 'timeout-up'),
                self._timeout_up
            )
        if self._timeout_down is not None:
            value_write(
                os.path.join(self._dir, 'timeout-down'),
                self._timeout_down
            )


class LongrunService(_AtomicService):
    """s6 long running service.
    """

    __slots__ = (
        '_default_down',
        '_finish_script',
        '_log_run_script',
        '_notification_fd',
        '_run_script',
        '_timeout_finish',
    )

    _TYPE = ServiceType.LongRun

    def __init__(self, directory, name,
                 run_script=None, finish_script=None, notification_fd=None,
                 log_run_script=None, timeout_finish=None, default_down=None,
                 dependencies=None, environ=None):
        super(LongrunService, self).__init__(
            directory,
            name,
            dependencies=dependencies,
            environ=environ
        )
        self._default_down = default_down
        self._finish_script = finish_script
        self._log_run_script = log_run_script
        self._notification_fd = notification_fd
        self._run_script = run_script
        self._timeout_finish = timeout_finish

    @property
    def type(self):
        return self._TYPE

    @property
    def logger_dir(self):
        """Returns the logger directory for the services.

        :returns ``str``:
            Full path to the service log directory.
        """
        return os.path.join(self._dir, 'log')

    @property
    def notification_fd(self):
        """s6 "really up" notification fd.
        """
        if self._notification_fd is None:
            self._notification_fd = value_read(
                os.path.join(self._dir, 'notification-fd'),
                default=-1
            )
        return self._notification_fd

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
            self._run_script = script_read(self._run_file)
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
                self._finish_script = script_read(self._finish_file)
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
                self._log_run_script = script_read(self._log_run_file)
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
        # XXX: FIXME
        if self._timeout_finish is None:
            self._timeout_finish = value_read(
                os.path.join(self._dir, 'timeout-finish'),
                default=5000
            )
        return self._timeout_finish

    def write(self):
        """Write down the service definition.
        """
        super(LongrunService, self).write()
        # Mandatory settings
        if self._run_script is None and not os.path.exists(self._run_file):
            raise ValueError('Invalid LongRun service: not run script')
        elif self._run_script is not None:
            script_write(self._run_file, self._run_script)
            # Handle the case where the run script is a generator
            if not isinstance(self._run_script, basestring):
                self._run_script = None
        # Optional settings
        if self._finish_script is not None:
            script_write(self._finish_file, self._finish_script)
            # Handle the case where the finish script is a generator
            if not isinstance(self._finish_script, basestring):
                self._finish_script = None
        if self._log_run_script is not None:
            # Create the log dir on the spot
            fs.mkdir_safe(os.path.dirname(self._log_run_file))
            script_write(self._log_run_file, self._log_run_script)
            # Handle the case where the run script is a generator
            if not isinstance(self._log_run_script, basestring):
                self._log_run_script = None
        if self._default_down:
            data_write(
                os.path.join(self._dir, 'down'),
                None
            )
        else:
            fs.rm_safe(os.path.join(self._dir, 'down'))
        if self._timeout_finish is not None:
            value_write(
                os.path.join(self._dir, 'timeout-finish'),
                self._timeout_finish
            )
        if self._notification_fd is not None:
            value_write(
                os.path.join(self._dir, 'notification-fd'),
                self._notification_fd
            )


__all__ = (
    'Service',
    'LongrunService',
)
