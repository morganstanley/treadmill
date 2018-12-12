"""Supervisor services management.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import errno
import logging
import os

import enum

from treadmill import fs

from . import _utils

_LOGGER = logging.getLogger(__name__)


class ServiceType(enum.Enum):
    """Types of services.
    """
    LongRun = 'longrun'
    Oneshot = 'oneshot'
    Bundle = 'bundle'


class Service:
    """Abstract base class of all services.
    """
    __slots__ = (
        '_dir',
        '_name',
    )

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
        _utils.data_write(os.path.join(self._dir, 'type'), self.type.value)

    @classmethod
    def read_dir(cls, directory):
        """Reads the type of service from the given directory.

        :returns ``(type, basedir, name) | None``:
            The type, base directory, and name of the service. Or None if not
            found.
        """
        svc_basedir = os.path.dirname(directory)
        svc_name = os.path.basename(directory)

        try:
            svc_type = _utils.data_read(os.path.join(directory, 'type'))
        except IOError as err:
            if err.errno is not errno.ENOENT:
                raise
            return None

        try:
            svc_type = ServiceType(svc_type)
        except ValueError:
            return None

        return svc_type, svc_basedir, svc_name


__all__ = (
    'Service',
)
