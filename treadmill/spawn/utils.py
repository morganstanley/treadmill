"""Treadmill spawn utilities."""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import pwd
import zlib

_LOGGER = logging.getLogger(__name__)


def get_user_safe(path):
    """Gets the user of the given path."""
    try:
        return pwd.getpwuid(os.stat(path).st_uid).pw_name
    except (OSError, KeyError):
        _LOGGER.warning('Could not get user of path %r', path)
        return None


def format_bucket(bucket):
    """Formats the bucket to a string."""
    return '{:06d}'.format(bucket)


def get_bucket_for_name(name, buckets):
    """Gets the bucket for the given name."""
    return format_bucket(zlib.crc32(name.encode('utf-8')) % buckets)


def get_instance_path(path, spawn_paths):
    """Gets the instance path for the app."""
    name = os.path.basename(path)
    if name.endswith('.yml'):
        name = name[:-4]
    bucket = get_bucket_for_name(name, spawn_paths.buckets)
    job_path = os.path.join(spawn_paths.jobs_dir, name)
    bucket_path = os.path.join(spawn_paths.running_dir, bucket)
    running_path = os.path.join(bucket_path, name)

    return job_path, bucket_path, running_path
