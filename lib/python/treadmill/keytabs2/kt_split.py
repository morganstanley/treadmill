"""
kt-split plugin to validate keytab
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import tempfile

from treadmill import fs
from treadmill import keytabs2
from treadmill import subproc

_LOGGER = logging.getLogger(__name__)

_NAME = 'keytab'


def validate_as_file(encoded_keytabs, basedir):
    """
    validate keytab by given encoded data

    return keytab files validated
    """
    temp_dir = tempfile.mkdtemp(dir=basedir)
    try:
        for encoded in encoded_keytabs:
            test_file = os.path.join(temp_dir, _NAME)
            keytabs2.write_keytab(
                test_file,
                encoded,
            )

            try:
                subproc.check_call(
                    ['kt_split', '--dir={}'.format(basedir), test_file]
                )
            except subproc.CalledProcessError:
                raise keytabs2.KeytabLockerError(
                    'wrong keytab data: {}'.format(encoded)
                )

        for kt_file in os.listdir(basedir):
            full_path = os.path.join(basedir, kt_file)
            # we ignore temp_dir in basedir
            if os.path.isdir(full_path):
                continue

            yield full_path

    finally:
        fs.rmtree_safe(temp_dir)
