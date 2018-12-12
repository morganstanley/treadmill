"""Base class for appcfg.features."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class Feature:
    """A manifest feature."""

    def __init__(self, tm_env):
        self._tm_env = tm_env

    @abc.abstractmethod
    def applies(self, manifest, runtime):
        """Configures the manifest with the feature.

        :param manifest:
            The Treadmill application manifest
        :type manifest:
            ``dict``
        :param runtime:
            The Treadmill runtime in effect
        :type runtime:
            ``str``
        :return:
            ``True`` if the given manifest applies
        """

    @abc.abstractmethod
    def configure(self, manifest):
        """Configures the manifest with the feature.

        :param manifest:
            The Treadmill application manifest
        :type manifest:
            ``dict``
        """
