"""Watchtower module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os

_SHARD_MAP = {
    'ny': 'na4',
    'vi': 'na3',
    'ln': 'eu1',
    'hk': 'apac1',
    'tk': 'jp1',
}


def get_shard():
    """Hardcoded logic find WT shard based on Region
    None prod shard (na1) should not be sent via localhost collector
    """

    # FIXME: need an elegant way to get WT shard
    campus = os.environ.get('SYS_CAMPUS')
    return _SHARD_MAP[campus]
