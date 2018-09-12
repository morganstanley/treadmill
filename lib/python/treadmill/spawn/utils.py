"""Treadmill spawn utilities.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import zlib

from treadmill import utils

_LOGGER = logging.getLogger(__name__)


def get_user_safe(path):
    """Gets the user of the given path.
    """
    try:
        return utils.get_username(os.stat(path).st_uid)
    except (OSError, KeyError):
        _LOGGER.warning('Could not get user of path %r', path)
        return None


def format_bucket(bucket):
    """Formats the bucket to a string.

    :params ``int`` bucket:
        Bucket number
    :returns:
        ``str`` - Formatted (0 padded) bucket number.
    """
    return '{:06d}'.format(bucket)


def get_bucket_for_name(name, buckets_nb):
    """Gets the bucket for the given name.

    :params ``str`` name:
        Name of the instance.
    :params ``int`` buckets_nb:
        Number of buckets
    """
    return format_bucket(zlib.crc32(name.encode()) % buckets_nb)


def get_instance_path(path, spawn_paths):
    """Gets the instance path for the app.
    """
    name = os.path.basename(path)
    if name.endswith('.yml'):
        name = name[:-4]
    bucket = get_bucket_for_name(name, spawn_paths.buckets)
    job_path = os.path.join(spawn_paths.jobs_dir, name)
    bucket_path = os.path.join(spawn_paths.running_dir, bucket)
    running_path = os.path.join(bucket_path, name)

    return job_path, bucket_path, running_path
