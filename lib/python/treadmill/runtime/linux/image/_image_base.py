"""The base implementation for managing images.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class Image:
    """Represents an image.
    """

    @abc.abstractmethod
    def unpack(self, container_dir, root_dir, app, app_cgroups):
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
        :param app_cgroups:
            The paths of app cgroups
        :type app_cgroups:
            ``dict``
        """
