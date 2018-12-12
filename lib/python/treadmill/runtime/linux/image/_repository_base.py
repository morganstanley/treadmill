"""The base implementation for a collection of images.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class ImageRepository:
    """A repository for images.
    """

    __slots__ = (
        'tm_env',
    )

    def __init__(self, tm_env):
        self.tm_env = tm_env

    @abc.abstractmethod
    def get(self, url):
        """Gets the image hosted at the given URL.

        :param url:
            The url of the image
        :type url:
            ``str``
        :return:
            An implementation of ``Image``
        :rtype:
            ``Image``
        """
