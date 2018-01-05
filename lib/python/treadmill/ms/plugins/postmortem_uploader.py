"""Postmortem uploader plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import getpass
import logging
import os
import pwd
import shutil

from treadmill import fs
from treadmill import utils

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import proiddb

_LOGGER = logging.getLogger(__name__)

DEFAULT_UPLOAD_DIR = '/v/region/{REGION}/appl/cloud/treadmill/data/' \
                     '{ENVIRONMENT}/nodeharvest-3'


def upload(archive_filename, upload_url=None):
    """Upload archive"""
    upload_user = os.environ['TREADMILL_ID']
    region = os.environ['SYS_REGION']
    pid = os.fork()
    if pid == 0:
        try:
            _LOGGER.info('Switching identity to %s', upload_user)
            if getpass.getuser() == 'root' and upload_user != 'root':
                pw = pwd.getpwnam(upload_user)
                os.setgroups([])
                os.setgid(pw.pw_gid)
                os.setuid(pw.pw_uid)
            _LOGGER.info('Preparing upload')
            if upload_url is None:
                upload_dir = DEFAULT_UPLOAD_DIR.format(
                    REGION=region,
                    ENVIRONMENT=proiddb.environment(upload_user),
                )
                fs.mkdir_safe(upload_dir, mode=0o755)
                dest_file = os.path.join(upload_dir,
                                         os.path.basename(archive_filename))
            else:
                dest_file = upload_url
            _LOGGER.info('Uploading to %s', dest_file)
            shutil.copyfile(archive_filename, dest_file)
            os.chmod(dest_file, 0o644)
            _LOGGER.info('Uploaded.')
        finally:
            utils.sys_exit(0)
    os.waitpid(pid, 0)
