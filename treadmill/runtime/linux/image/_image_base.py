"""The base implementation for managing images."""

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class Image(object):
    """Represents an image."""

    @abc.abstractmethod
    def unpack(self, container_dir, root_dir, app):
        """Unpacks the image to the root dir.

        :param container_dir:
            The root path of the container.
        :type container_dir:
            ``str``
        :param root_dir:
            The root path to unpack the image
        :type root_dir:
            ``str``
        :param app:
            The application manifest
        :type app:
            ``dict``
        """
        pass
