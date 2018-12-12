"""Helper functions for a treadmill websocket client.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import functools
import logging

from treadmill.websocket import client as wsc
from treadmill.trace.app import events

_LOGGER = logging.getLogger(__name__)


def _filter_by_uniq(in_=None, out_=None, uniq=None):
    """Only keep the events that belong to the 'uniq' in params."""
    event = events.AppTraceEvent.from_dict(in_['event'])

    if event is None:
        return True

    if uniq is not None and getattr(event, 'uniqueid', None) != uniq:
        return True

    out_.append(event)
    return True


def _get_instance_trace(instance, uniq, ws_api):
    """Get the history of the given instance/uniq."""
    rv = []
    message = {'topic': '/trace', 'filter': instance, 'snapshot': True}
    on_message = functools.partial(_filter_by_uniq, out_=rv, uniq=uniq)

    wsc.ws_loop(ws_api, message, True, on_message)

    return rv


def find_uniq_instance(instance, uniq, ws_api):
    """Find the host and container id of a terminated or running app."""
    if uniq == 'running':
        uniq = None

    history = _get_instance_trace(instance, uniq, ws_api)
    _LOGGER.debug('Instance %s/%s trace: %s', instance, uniq, history)

    # keep only those items from which uniq can be found out
    history = [item for item in history if hasattr(item, 'uniqueid')]

    if not history:
        return {}

    def get_timestamp(obj):
        """Get the timestamp attribute of the object."""
        return getattr(obj, 'timestamp', None)

    last = max(history, key=get_timestamp)
    _LOGGER.debug('Instance %s\'s last trace item: %s', instance, last)
    return {'instanceid': last.instanceid,
            'host': getattr(last, 'source', None),
            'uniq': getattr(last, 'uniqueid', None)}


def _instance_to_host(in_=None, out_=None):
    """Update out_ so it contains 'instance: host' as key: value pairs."""
    if 'host' not in in_:
        return True

    out_.update({'instanceid': in_['name'],
                 'host': in_['host'],
                 'uniq': 'running'})
    return False


def find_running_instance(app, ws_api):
    """Find the instance name and host corresponding to a running app."""
    rv = {}
    message = {'topic': '/endpoints',
               'filter': app,
               'proto': 'tcp',
               'endpoint': 'ssh',
               'snapshot': True}

    on_message = functools.partial(_instance_to_host, out_=rv)

    wsc.ws_loop(ws_api, message, True, on_message)

    return rv
