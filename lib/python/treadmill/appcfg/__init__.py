"""Manages Treadmill applications lifecycle.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import string

import enum

from treadmill import utils

_LOGGER = logging.getLogger(__name__)

APP_JSON = 'app.json'


class AppType(enum.Enum):
    """The type of application."""
    NATIVE = 'native'
    TAR = 'tar'
    DOCKER = 'docker'

    @staticmethod
    def get_app_type(image):
        """Checks if the type name is valid."""
        if not image:
            return AppType.NATIVE

        if image.startswith('native:'):
            return AppType.NATIVE

        if image.startswith('http://'):
            return AppType.TAR

        if image.startswith('file://'):
            return AppType.TAR

        if image.startswith('docker://'):
            return AppType.DOCKER

        raise Exception('Invalid image type: {0}'.format(image))


def gen_uniqueid(event_file):
    """Generate a uniqueid for a given event file

    Uniqueid needs to be length constrained (exactly 13 char) and character set
    constrained ([a-z0-9]) to avoid issues with the naming limitations of the
    different resources of the container (root dir, logical volume, virtual
    ethernet device, ...)

    The current smallest length limiter is:

        virtual ethernet device(13): IFNAMESZ 16 char
                                     - 1 (zero terminated)
                                     - 2 ('.0'/'.1' suffix)

    This function will output an unique identifier of a maximum of 13 chars
    by encoding the event's instance_id, inode number and ctime in base 62.

    :param event_file:
        Full path to an event file
    :type event_file:
        ``str``
    :returns:
        (``str``) -- 13 chars identifier
    """

    event_stat = os.stat(event_file)
    # Event time is the creation time in millisec
    event_time = int(event_stat.st_ctime * 10**6)

    # Event data is the event inode (64bit) combined with the instance id
    # (33bit)
    # Why: InstanceID is 10 digits:
    #      int(10 * math.log(10) / math.log(2)) -> 33
    event_data = int(event_stat.st_ino)
    _name, _sep, instance = os.path.basename(event_file).rpartition('#')
    event_data ^= (int(instance) << 31)
    event_data &= (2 ** 64) - 1

    seed = (event_time << 64) + int(event_data)

    # Trim the top bits so that we only consider 77bits.
    # Note we trim from the ctime high bits.
    # Why: int(13 * math.log(62) / math.log(2)) -> 77
    seed &= (2 ** 77) - 1

    numerals = string.digits + string.ascii_lowercase + string.ascii_uppercase
    ret = utils.to_base_n(seed, base=len(numerals), alphabet=numerals)

    return '{identifier:>013s}'.format(identifier=ret)


def _fmt_unique_name(appname, app_uniqueid):
    """Format app data into a unique app name.
    """
    return '{app}-{id:>013s}'.format(
        app=appname.replace('#', '-'),
        id=app_uniqueid,
    )


def app_unique_name(app):
    """Unique app name for a given app object.
    """
    return _fmt_unique_name(app.name, app.uniqueid)


def manifest_unique_name(manifest):
    """Unique app name for a given app manifest dictionary.
    """
    return _fmt_unique_name(manifest['name'], manifest['uniqueid'])


def eventfile_unique_name(eventfile):
    """Unique app name for a given event file object.
    """
    uniqueid = gen_uniqueid(eventfile)
    name = os.path.basename(eventfile)
    return _fmt_unique_name(name, uniqueid)


def appname_task_id(appname):
    """Returns the task id from app instance name."""
    _appname, taskid = appname.split('#')
    return taskid


def appname_basename(appname):
    """Returns the base name of the app instance without instance id."""
    basename, _taskid = appname.split('#')
    return basename


def app_name(uniquename):
    """Format app name given its unique name.
    """
    appname = uniquename.rsplit('-', 1)[0]
    parts = appname.rsplit('-', 1)
    return '#'.join(parts)


def app_unique_id(uniquename):
    """Returns the unique id from app unique name."""
    return uniquename.rsplit('-', 1)[1]
