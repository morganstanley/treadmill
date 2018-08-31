"""Send events via uds
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import socket
import time

from treadmill import osnoop

_LOGGER = logging.getLogger(__name__)


@osnoop.windows
def post_ipc(event, uds='/run/tm_ctl/appevents'):
    """Post events to UCSPI socket
    Most use case is to send container event from inside container
    """
    _LOGGER.debug('post: %s: %r', uds, event)
    (
        _ts,
        _src,
        instanceid,
        event_type,
        event_data,
        _payload
    ) = event.to_data()

    event_str = '{},{},{},{}'.format(
        time.time(), instanceid, event_type, event_data
    ).encode()

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as u_sock:
        try:
            u_sock.connect(uds)
            u_sock.sendall(event_str)

        except ConnectionRefusedError:
            _LOGGER.error('unable to connect %s', uds)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error('error to send event %s: %r', event_str, err)
