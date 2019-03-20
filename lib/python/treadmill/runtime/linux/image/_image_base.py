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
    def unpack(self, container_dir, root_dir, app, app_cgroups, data):
        """Unpacks the image to the root dir.

        :param ``str`` container_dir:
            The root path of the container.
        :param ``str`` root_dir:
            The root path to unpack the image.
        :param ``dict`` app:
            The application manifest.
        :param ``dict`` app_cgroups:
            The paths of app cgroups.
        :param ``dict`` data:
            Local configuration data.
        """
