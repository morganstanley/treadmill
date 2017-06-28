"""S6 service directory management.
"""

from __future__ import absolute_import

import errno
import logging
import os

from treadmill import fs

from . import services
from ._utils import (
    script_read,
    script_write,
)

_LOGGER = logging.getLogger(__name__)


class ServiceDir(object):
    """Models an s6 service directory.
    """
    __slots__ = (
        '_crash',
        '_dir',
        '_finish',
        '_services',
    )

    def __init__(self, directory):
        self._dir = directory
        fs.mkdir_safe(self._dir)
        fs.mkdir_safe(os.path.join(self._dir, '.s6-svscan'))
        self._crash = None
        self._finish = None
        self._services = None

    def __repr__(self):
        return '{type}({dir!r})'.format(
            type=self.__class__.__name__,
            dir=os.path.basename(self._dir),
        )

    @property
    def directory(self):
        """Gets the s6 service directory path.
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
                    services.Service.from_dir(os.path.join(self._dir, name))
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

        svc = services.Service.new(
            svc_basedir=self._dir,
            svc_name=svc_name,
            svc_type=svc_type,
            **kw_args
        )
        self._services[svc.name] = svc
        return svc

    @property
    def _finish_file(self):
        return os.path.join(self._dir, '.s6-svscan', 'finish')

    @property
    def finish(self):
        """Gets the s6-svscan finish script.
        """
        if self._finish is None:
            try:
                self._finish = script_read(self._finish_file)
            except IOError as err:
                if err.errno is not errno.ENOENT:
                    raise
        return self._finish

    @finish.setter
    def finish(self, new_script):
        """Sets the s6-svscan finish script.
        """
        self._finish = new_script

    @property
    def _crash_file(self):
        return os.path.join(self._dir, '.s6-svscan', 'crash')

    @property
    def crash(self):
        """Get the contents of the crash file.
        """
        if self._crash is None:
            try:
                self._crash = script_read(self._crash_file)
            except IOError as err:
                if err.errno is not errno.ENOENT:
                    raise
        return self._crash

    @crash.setter
    def crash(self, new_script):
        self._crash = new_script

    def write(self):
        """Write down the service definition.
        """
        if self._finish is not None:
            script_write(self._finish_file, self._finish)
        if self._crash is not None:
            script_write(self._crash_file, self._crash)
        if self._services is not None:
            for svc in self._services.values():
                svc.write()

    @classmethod
    def from_dir(cls, directory):
        """Constructs a service dir from an existing directory.
        """
        return cls(directory=os.path.realpath(directory))


__all__ = (
    'ServiceDir',
)
