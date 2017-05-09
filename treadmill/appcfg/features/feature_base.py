"""Base class for appcfg.features."""

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class Feature(object):
    """A manifest feature."""

    @abc.abstractmethod
    def applies(self, manifest):
        """Configures the manifest with the feature.

        :param manifest:
            The Treadmill application manifest
        :type manifest:
            ``dict``
        :return:
            ``True`` if the given manifest applies
        """
        pass

    @abc.abstractmethod
    def configure(self, manifest):
        """Configures the manifest with the feature.

        :param manifest:
            The Treadmill application manifest
        :type manifest:
            ``dict``
        """
        pass
