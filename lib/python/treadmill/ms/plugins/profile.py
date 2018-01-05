"""Context plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os


def api_scope():
    """Returns admin API DNS scope."""
    if os.name == 'nt':
        return [os.environ.get('REGIONCODE', 'na') + '.' + 'region',
                'na.region']
    else:
        return [os.environ.get('SYS_REGION', 'na') + '.' + 'region',
                'na.region']


PROFILE = {
    'api_scope': api_scope(),
    'dns_domain': 'treadmill.ms.com',
    'ldap_suffix': 'dc=ms,dc=com',
    'scopes': ['campus', 'region'],
    'api.instance.plugins': ['ms-proid-env'],
    'api.allocation.plugins': ['ms-rank-adjustment'],
}
