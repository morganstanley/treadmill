"""Supervision scan directory management.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc
import errno
import logging
import os
import sys

import six

from treadmill import fs

from . import _service_base
from . import _utils


_LOGGER = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class ScanDir:
    """Models a service directory.
    """
    __slots__ = (
        '_dir',
        '_control_dir',
        '_services',
    )

    def __init__(self, directory):
        self._dir = directory
        self._control_dir = os.path.join(self._dir, self.control_dir_name())
        self._services = None

    @staticmethod
    @abc.abstractmethod
    def _create_service(svc_basedir, svc_name, svc_type, **kwargs):
        """Implementation specifc service object creation from service data.
        """

    @staticmethod
    @abc.abstractmethod
    def control_dir_name():
        """Gets the name of the svscan control directory.
        """

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
            self._services = {}

            try:
                for name in os.listdir(self._dir):
                    if name[0] == '.':
                        continue

                    dir_path = os.path.join(self._dir, name)
                    if not os.path.isdir(dir_path):
                        continue

                    svc_data = _service_base.Service.read_dir(dir_path)
                    if svc_data is None:
                        continue

                    svc_type, svc_basedir, svc_name = svc_data
                    svc = self._create_service(
                        svc_basedir=svc_basedir,
                        svc_name=svc_name,
                        svc_type=svc_type
                    )
                    # Should never fail to create the svc object
                    self._services[svc.name] = svc

            except OSError as err:
                if err.errno == errno.ENOENT:
                    pass
                else:
                    six.reraise(*sys.exc_info())

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

    def write(self):
        """Write down the service definition.
        """
        fs.mkdir_safe(self._control_dir)
        if self._services is not None:
            for svc in self._services.values():
                svc.write()

    @classmethod
    def add_ctrlfile_props(cls):
        """Define all the properties for slot'ed attributes.
        """
        def _add_ctrlfile_prop(cls, attrib):
            """Add all the class properties for a given file attribute.
            """
            attrib_filename = '%s_file' % attrib

            def _getter(self):
                """Gets the svscan {filename} control script.
                """
                if getattr(self, attrib) is None:
                    try:
                        setattr(
                            self,
                            attrib,
                            _utils.script_read(
                                getattr(self, attrib_filename)
                            )
                        )
                    except IOError as err:
                        if err.errno is not errno.ENOENT:
                            raise
                return getattr(self, attrib)

            def _setter(self, new_script):
                """Sets the svscan {filename} control script.
                """
                setattr(
                    self,
                    attrib,
                    new_script
                )

            _getter.__doc__ = _getter.__doc__.format(filename=attrib[1:])
            attrib_prop = property(_getter)

            _setter.__doc__ = _setter.__doc__.format(filename=attrib[1:])
            attrib_prop = attrib_prop.setter(_setter)

            setattr(cls, attrib[1:], attrib_prop)

        for attrib in cls.__slots__:
            _add_ctrlfile_prop(cls, attrib)


__all__ = (
    'ScanDir',
)
