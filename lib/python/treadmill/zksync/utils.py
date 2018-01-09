"""ZKSync utilities.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import tempfile
import time

from treadmill import utils

MODIFIED = '.modified'


_LOGGER = logging.getLogger(__name__)


def create_ready_file(fsroot):
    """Create zksync ready file
    """
    modified_file = os.path.join(fsroot, '.modified')
    utils.touch(modified_file)
    return modified_file


def write_data(fpath, data, modified, raise_err=True, tmp_dir=None):
    """Safely write data to file path.
    """
    tmp_dir = tmp_dir or os.path.dirname(fpath)
    with tempfile.NamedTemporaryFile(dir=tmp_dir,
                                     delete=False,
                                     prefix='.tmp') as temp:
        if data:
            temp.write(data)
        if os.name == 'posix':
            os.fchmod(temp.fileno(), 0o644)
    os.utime(temp.name, (modified, modified))
    try:
        os.rename(temp.name, fpath)
    except OSError:
        _LOGGER.error('Unable to rename: %s => %s', temp.name, fpath,
                      exc_info=True)
        if raise_err:
            raise


def wait_for_ready(fs_root):
    """Wait for modified file to appear to indicate zksync ready
    """
    modified = os.path.join(fs_root, MODIFIED)
    while not os.path.exists(modified):
        _LOGGER.info('zk2fs mirror does not exist, waiting.')
        time.sleep(1)

    return modified
