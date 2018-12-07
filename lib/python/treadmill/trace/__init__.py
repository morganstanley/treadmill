"""Treadmill trace.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import socket
import time

import six

from treadmill import fs
from treadmill import osnoop
from treadmill import yamlwrapper as yaml

from treadmill.trace.app import events as app_events
from treadmill.trace.app import zk as app_zk
from treadmill.trace.server import events as server_events
from treadmill.trace.server import zk as server_zk


_LOGGER = logging.getLogger(__name__)


def post(events_dir, event):
    """Post event to event directory.
    """
    _LOGGER.debug('post: %s: %r', events_dir, event)

    (
        _ts,
        _src,
        what,
        event_type,
        event_data,
        payload
    ) = event.to_data()

    filename = '%s,%s,%s,%s' % (
        time.time(),
        what,
        event_type,
        event_data
    )

    def _write_temp(temp):
        if payload is None:
            pass
        elif isinstance(payload, six.string_types):
            temp.write(payload)
        else:
            yaml.dump(payload, stream=temp)

    fs.write_safe(
        os.path.join(events_dir, filename),
        _write_temp,
        prefix='.tmp',
        mode='w',
        permission=0o644
    )


@osnoop.windows
def post_ipc(uds, event):
    """Post event to UCSPI socket.

    Can be used to send event from inside container, ignores payload.
    """
    _LOGGER.debug('post_ipc: %s: %r', uds, event)

    (
        _ts,
        _src,
        what,
        event_type,
        event_data,
        _payload
    ) = event.to_data()

    event_str = '{},{},{},{}'.format(
        time.time(), what, event_type, event_data
    ).encode()

    sent = 0
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as u_sock:
        try:
            u_sock.connect(uds)
            u_sock.sendall(event_str)
            sent = len(event_str)

        except ConnectionRefusedError:
            _LOGGER.error('unable to connect %s', uds)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error('error to send event %s: %r', event_str, err)

    return sent


def post_zk(zkclient, event):
    """Post and publish event directly to ZK.

    Can be used to send event without event directory/UCSPI socket.
    """
    _LOGGER.debug('post_zk: %r', event)

    (
        _ts,
        _src,
        what,
        event_type,
        event_data,
        payload
    ) = event.to_data()

    if isinstance(event, app_events.AppTraceEvent):
        publish = app_zk.publish
    elif isinstance(event, server_events.ServerTraceEvent):
        publish = server_zk.publish
    else:
        _LOGGER.warning('Unknown event type %r', type(event))
        return

    publish(zkclient, str(time.time()), what, event_type, event_data, payload)
