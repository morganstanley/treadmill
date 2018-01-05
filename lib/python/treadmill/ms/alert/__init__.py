"""Services and utilities used to send alerts through masters to watchtower.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import pprint
import os
import tempfile

import six

from treadmill import fs
from treadmill import sysinfo
from treadmill import yamlwrapper as yaml

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms.watchtower import api as wtapi

_LOGGER = logging.getLogger(__name__)

FACET = 'CONTAINER'


def send_event(event_type, instanceid, summary, **kwargs):
    """Send event to Watchtower, kwargs items are pushed in event payload
    """
    payload = {
        'summary': summary,
    }
    for key, value in six.iteritems(kwargs):
        # make sure value is string
        payload[key] = str(value)

    _LOGGER.debug(
        'Sending alert to Watchtower %s:%s:\n %s',
        event_type,
        instanceid,
        pprint.pformat(payload)
    )
    resource = wtapi.get_proid_resource(os.environ.get('TREADMILL_ID'))
    wtapi.send_single_event(FACET, resource, event_type, payload, instanceid)
