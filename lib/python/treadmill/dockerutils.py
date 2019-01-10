"""Docker helper functions.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import utils

_DEFAULT_ULIMIT = ['core', 'data', 'fsize', 'nproc', 'nofile', 'rss', 'stack']


def init_ulimit(ulimit=None):
    """Initialize dockerd ulimits to parent process ulimit defaults.
       Accepts an optional list of overrides.
    """
    total_result = []

    for u_type in _DEFAULT_ULIMIT:
        (soft_limit, hard_limit) = utils.get_ulimit(u_type)
        total_result.append(
            {'Name': u_type, 'Soft': soft_limit, 'Hard': hard_limit}
        )

    if ulimit:
        for u_string in ulimit:
            (u_type, soft_limit, hard_limit) = u_string.split(':', 3)
            for limit in total_result:
                if limit['Name'] == u_type:
                    limit['Soft'] = int(soft_limit)
                    limit['Hard'] = int(hard_limit)

    return total_result


def fmt_ulimit_to_flag(ulimits):
    """Format rich dictionary to dockerd-compatible cli flags.

       Do not respect "soft" limit as dockerd has a known issue when comparing
       finite vs infinite values; will error on {Soft=0, Hard=-1}
    """
    total_result = []
    for flag in ulimits:
        total_result.append('--default-ulimit {}={}:{}'.format(flag['Name'],
                                                               flag['Hard'],
                                                               flag['Hard']))
    return ' '.join(total_result)
