"""Supervision scan directory management.
"""

from __future__ import absolute_import

import abc
import errno
import logging
import os

import six

from treadmill import fs

from . import _service_base
from . import _utils


_LOGGER = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class ScanDir(object):
    """Models a service directory.
    """
    __slots__ = (
        '_dir',
        '_control_dir',
        '_finish',
        '_services',
        '_create_service',
    )

    def __init__(self, directory, control_dir, create_service):
        self._dir = directory
        self._control_dir = os.path.join(self._dir, control_dir)
        fs.mkdir_safe(self._control_dir)
        self._finish = None
        self._services = None
        self._create_service = create_service

    def __repr__(self):
        return '{type}({dir!r})'.format(
            type=self.__class__.__name__,
            dir=os.path.basename(self._dir),
        )

    def control_dir(self):
        """Gets the svscan control directory.
        """
        return self._control_dir

    @property
    def directory(self):
        """Gets the service directory path.
        """
        return self._dir

    @property
    def services(self):
        """Gets the services which this service directory is composed of.
        """
        if self._services is None:
            self._services = {
                svc.name: svc
                for svc in (
                    _service_base.Service.read_dir(
                        os.path.join(self._dir, name), self._create_service)
                    for name in os.listdir(self._dir)
                    if not name.startswith('.')
                )
                if svc is not None
            }
        return self._services.copy()

    def add_service(self, svc_name, svc_type, **kw_args):
        """Adds a service to the service directory.
        """
        if self._services is None:
            # Pre-warm the services dict
            _s = self.services

        svc = self._create_service(
            svc_basedir=self._dir,
            svc_name=svc_name,
            svc_type=svc_type,
            **kw_args
        )
        self._services[svc.name] = svc
        return svc

    @property
    def _finish_file(self):
        return os.path.join(self._control_dir, 'finish')

    @property
    def finish(self):
        """Gets the svscan finish script.
        """
        if self._finish is None:
            try:
                self._finish = _utils.script_read(self._finish_file)
            except IOError as err:
                if err.errno is not errno.ENOENT:
                    raise
        return self._finish

    @finish.setter
    def finish(self, new_script):
        """Sets the svscan finish script.
        """
        self._finish = new_script

    def write(self):
        """Write down the service definition.
        """
        if self._finish is not None:
            _utils.script_write(self._finish_file, self._finish)
        if self._services is not None:
            for svc in self._services.values():
                svc.write()


__all__ = (
    'ScanDir',
)
