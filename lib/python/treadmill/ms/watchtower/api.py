"""Watchtower API wrapper.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time
import uuid

import six

if six.PY2:
    import functools32 as functools  # pylint: disable=import-error
else:
    import functools  # pylint: disable=wrong-import-order

from wt.publisher import thread as wtpb
from wt.publisher import blocking as wtblpb
from wt import ident
from wt.response import status as res_status

from treadmill.ms import watchtower
from treadmill.ms import proiddb

_LOGGER = logging.getLogger(__name__)

NAMESPACE_WT = uuid.UUID('6ba7b815-9dad-11d1-80b4-00c04fd430c8')
WT_HOST = 'localhost'
WT_PORT = 13684


if six.PY3:
    def _uuid5_str(finger_str):
        """Returns a string UUID5 of the given fingerprint in the WatchTower
        namespace.

        :params ``str`` finger_str:
            Unicode fingerprint string of the event.
        """
        return str(uuid.uuid5(NAMESPACE_WT, finger_str))

else:
    def _uuid5_str(finger_str):
        """Returns a string UUID5 of the given fingerprint in the WatchTower
        namespace.

        :params ``str`` finger_str:
            Unicode fingerprint string of the event.
        """
        return str(uuid.uuid5(NAMESPACE_WT, finger_str.encode()))


def _event_finger(item_key, instance, timestamp, payload):
    """return deterministic uuid of the event
    """
    # hash(fronzenset()) is the lightest way to get finger of payload
    finger_str = '{}/{}/{}/{}'.format(
        item_key, instance, timestamp, hash(frozenset(payload.items()))
    )
    return _uuid5_str(finger_str)


def _metric_finger(item_key, instance, timestamp):
    """return deterministic uuid of the metric.
    """
    finger_str = '{}/{}/{}'.format(
        item_key, instance, timestamp
    )
    return _uuid5_str(finger_str)


@functools.lru_cache(maxsize=100)
def _get_proid_eonid_env(proid):
    """Store at most 100 proid -> (env, eonid) cache
    """
    eonid = proiddb.eonid(proid)
    env = proiddb.environment(proid)
    return (eonid, env)


def get_proid_resource(proid):
    """Get Watchtower container resource name from proid
    """
    (eonid, env) = _get_proid_eonid_env(proid)

    # TODO: need to deal with personal container
    if eonid is None or env is None:
        return None

    shard = watchtower.get_shard()
    # do not need env in container name as it is container event
    return '{}-container-{}-{}'.format(eonid, proid, shard)


def _get_resource(instanceid):
    """ return proper WT resource name of instance """
    proid = instanceid[0:instanceid.find('.')]

    return get_proid_resource(proid)


class MetricsSender(object):
    """API wrapper to send metrics
    """
    def __init__(self, cell, facet, host=WT_HOST, port=WT_PORT):
        self._publisher = wtpb.ThreadPublisher(host, port)
        self._facet = facet
        self._cell = cell

        publisher = self._publisher

        @publisher.on_metric_result
        def _callback(results, _act):
            for result in results:
                if result.status == \
                        res_status.ResponseStatusCode.UNKNOWN_IDENTITY:
                    try:
                        publisher.refresh_ident(result.resource_id)
                    except ident.IdentError as _err:
                        # unable to re-register resource id
                        _LOGGER.error('[%s] Ident error, abort',
                                      result.uuid)
                        publisher.remove_metric(result.uuid)
                elif result.status == res_status.ResponseStatusCode.LATER:
                    _LOGGER.warning(
                        '[%s] Collector busy, try later', result.uuid
                    )
                elif result.status == res_status.ResponseStatusCode.DUPLICATE:
                    _LOGGER.debug('[%s] Duplicate, abort', result.uuid)
                    publisher.remove_metric(result.uuid)
                elif result.status != res_status.ResponseStatusCode.OK:
                    _LOGGER.error('[%s] Critical error %d(%s), abort',
                                  result.uuid, result.status, result.message)
                    publisher.remove_metric(result.uuid)
                else:
                    _LOGGER.debug('[%s] Success', result.uuid)

            _LOGGER.debug('WT response processed')

    def dispatch(self):
        """ dispatch the result from WT collecor """
        self._publisher.dispatch()
        # send events anyway, as long as we have free cycle
        self._publisher.send_metrics()

    def send(self, item_key, value, instanceid, metric_time=None):
        """ add metrics to wt publisher """

        resource = _get_resource(instanceid)
        if resource is None:
            _LOGGER.warning(
                'Failed to get resource, abort sending to WatchTower'
            )
            return

        facet = self._facet
        try:
            self._publisher.ensure_ident(facet, resource)
        except ident.IdentError as err:
            _LOGGER.error('Unable to ident %s:%s: %r', facet, resource, err)
            return

        instance = '{}/{}'.format(self._cell, instanceid)

        clock = int(metric_time * 1000
                    if metric_time else time.time() * 1000)
        uuid_finger = _metric_finger(item_key, instance, clock)
        uuid_finger = self._publisher.add_metric(
            facet, resource, item_key, value, clock, uuid_finger, instance
        )
        # if metric not added, we must send to free flatbuffer cache
        # if metric is addded, we send events anyway in case we have free cycle
        published = self._publisher.send_metrics()

        # if not added, it means buffer is full,
        # we must wait for metric published
        if not published:
            if not uuid_finger:
                # not published means transport layer is busy
                # wait for http send next event request
                while not self._publisher.send_metrics():
                    time.sleep(1)


class EventSender(object):
    """API wrapper to send event
    """

    def __init__(self, cell, facet, host=WT_HOST, port=WT_PORT):
        _LOGGER.info('connecting to WT collector %s:%d', host, port)
        self._publisher = wtpb.ThreadPublisher(host, port)
        self._facet = facet
        self._cell = cell
        publisher = self._publisher

        @publisher.on_event_result
        def _callback(results, _act):
            for result in results:
                if result.status == \
                        res_status.ResponseStatusCode.UNKNOWN_IDENTITY:
                    try:
                        publisher.refresh_ident(result.resource_id)
                    except ident.IdentError as _err:
                        # unable to re-register resource id
                        _LOGGER.error('[%s] Ident error, abort',
                                      result.uuid)
                        publisher.remove_event(result.uuid)
                elif result.status == res_status.ResponseStatusCode.LATER:
                    _LOGGER.warning(
                        '[%s] Collector busy, try later', result.uuid
                    )
                elif result.status == res_status.ResponseStatusCode.DUPLICATE:
                    _LOGGER.debug('[%s] Duplicate, abort', result.uuid)
                    publisher.remove_event(result.uuid)
                elif result.status != res_status.ResponseStatusCode.OK:
                    _LOGGER.error('[%s] Critical error %d(%s), abort',
                                  result.uuid, result.status, result.message)
                    publisher.remove_event(result.uuid)
                else:
                    _LOGGER.debug('[%s] Success', result.uuid)

            _LOGGER.debug('WT response processed')

    def dispatch(self):
        """Dispatch the result from WT collecor
        """
        self._publisher.dispatch()
        # send events anyway, as long as we have free cycle
        self._publisher.send_events()

    def send(self, item_key, payload, instanceid, event_time=None):
        """Add event to wt publisher
        """
        resource = _get_resource(instanceid)
        if resource is None:
            _LOGGER.warning(
                'Failed to get resource, abort sending to WatchTower'
            )
            return

        # watchtower payload value must be string but cannot be empty string
        payload = {key: str(val) for key, val in payload.items()
                   if val is not None and val != ''}

        facet = self._facet

        # watchtower accept time in milisecond
        clock = int(event_time * 1000
                    if event_time else time.time() * 1000)

        instance = '{}/{}'.format(self._cell, instanceid)
        uuid_finger = _event_finger(item_key, instance, clock, payload)

        _LOGGER.debug(
            'send event: facet[%s], resource[%s], item_key[%s], ' +
            'instance[%s], clock[%d], uuid[%s]: %r',
            facet, resource, item_key, instance, clock, uuid_finger, payload
        )

        try:
            self._publisher.ensure_ident(facet, resource)
        except ident.IdentError as err:
            _LOGGER.error('Unable to ident %s:%s: %r', facet, resource, err)
            return

        uuid_finger = self._publisher.add_event(
            facet, resource, item_key, payload, clock, uuid_finger, instance
        )
        # if event not added, we must send to free flatbuffer cache
        # if event is addded, we send events anyway in case we have free cycle
        published = self._publisher.send_events()

        # if not added, it means buffer is full,
        # we must wait for event published
        if not published:
            if not uuid_finger:
                # not published means transport layer is busy
                # wait for http send next event request
                while not self._publisher.send_events():
                    time.sleep(1)


def send_single_event(facet, resource, item_key, payload, instanceid,
                      event_time=None, host=WT_HOST, port=WT_PORT):
    """Safely to send a single event to Watchtower
    """
    publisher = wtblpb.BlockingPublisher(host, port)
    publisher.ensure_ident(facet, resource)

    clock = int(event_time * 1000
                if event_time else time.time() * 1000)

    event_uuid = publisher.add_event(
        facet=facet,
        resource=resource,
        item_key=item_key,
        payload=payload,
        clock=clock,
        instance=instanceid,
    )
    if event_uuid is None:
        raise Exception('buffer is full')

    while True:
        published = publisher.send_events()

        # nothing to send
        if published is None:
            break

        (results, _act) = published

        # if no results, it mays event accepted without any complaint from WT
        if not results:
            break

        result = results[0]
        if result.status == res_status.ResponseStatusCode.UNKNOWN_IDENTITY:
            try:
                publisher.refresh_ident(result.resource_id)
            except ident.IdentError as _err:
                # unable to re-register resource id
                publisher.remove_event(result.uuid)
        elif result.status == res_status.ResponseStatusCode.LATER:
            _LOGGER.debug('try later %s', result.uuid)
        elif result.status != res_status.ResponseStatusCode.OK:
            # also you can do something different
            _LOGGER.debug('critical error, removing %r', result)
            publisher.remove_event(result.uuid)
        else:
            _LOGGER.debug('sent %s, %s', result.uuid, result.message)

        _LOGGER.info('Response Processed')

    return event_uuid
