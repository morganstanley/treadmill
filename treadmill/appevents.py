"""Process application events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os
import time

import kazoo.client
import six

from treadmill import fs
from treadmill import dirwatch
from treadmill import sysinfo
from treadmill import utils
from treadmill import yamlwrapper as yaml
from treadmill import zknamespace as z
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)

_SERVERS_ACL = zkutils.make_role_acl('servers', 'rwcda')

_HOSTNAME = sysinfo.hostname()


def _publish_zk(zkclient, when, instanceid, event_type, event_data, payload):
    """Publish application event to ZK.
    """
    eventnode = '%s,%s,%s,%s' % (when, _HOSTNAME, event_type, event_data)
    _LOGGER.debug('Creating %s', z.path.trace(instanceid, eventnode))
    try:
        zkutils.with_retry(
            zkutils.create,
            zkclient,
            z.path.trace(instanceid, eventnode),
            payload,
            acl=[_SERVERS_ACL]
        )
    except kazoo.client.NodeExistsError:
        pass

    if event_type in ['aborted', 'killed', 'finished']:
        # For terminal state, update the finished node with exit summary.
        zkutils.with_retry(
            zkutils.put,
            zkclient,
            z.path.finished(instanceid),
            {'state': event_type,
             'when': when,
             'host': _HOSTNAME,
             'data': event_data},
            acl=[_SERVERS_ACL],
        )

        _unschedule(zkclient, instanceid)


def _unschedule(zkclient, instanceid):
    """Safely delete scheduled node."""
    scheduled_node = z.path.scheduled(instanceid)

    # Check placement node. Only delete scheduled app if it is currently
    # placed on the server.
    #
    # If we are processing stale events, app can be placed elsewhere, and in
    # this case this server does not own placement and should not delete
    # scheduled node.
    placement_node = z.path.placement(_HOSTNAME, instanceid)

    if zkclient.exists(placement_node):
        _LOGGER.info('Unscheduling: %s', scheduled_node)
        zkutils.with_retry(
            zkutils.ensure_deleted, zkclient,
            scheduled_node
        )
    else:
        _LOGGER.info('Stale event, placement does not exist: %s',
                     placement_node)


def post_zk(zkclient, event):
    """Post and publish application event directly to ZK.

    Can be used if event directory is unknown (i.e. master/scheduler "API").
    """
    _LOGGER.debug('post_zk: %r', event)

    (
        _ts,
        _src,
        instanceid,
        event_type,
        event_data,
        payload
    ) = event.to_data()
    _publish_zk(
        zkclient, str(time.time()), instanceid, event_type, event_data, payload
    )


def post(events_dir, event):
    """Post application event to event directory.
    """
    _LOGGER.debug('post: %s: %r', events_dir, event)

    (
        _ts,
        _src,
        instanceid,
        event_type,
        event_data,
        payload
    ) = event.to_data()
    filename = '%s,%s,%s,%s' % (
        time.time(),
        instanceid,
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
        prefix='.tmp'
    )


class AppEventsWatcher(object):
    """Publish app events from the queue."""

    def __init__(self, zkclient, events_dir):
        self.zkclient = zkclient
        self.events_dir = events_dir

    def run(self):
        """Monitores events directory and publish events."""

        watch = dirwatch.DirWatcher(self.events_dir)
        watch.on_created = self._on_created

        for eventfile in os.listdir(self.events_dir):
            filename = os.path.join(self.events_dir, eventfile)
            self._on_created(filename)

        while True:
            if watch.wait_for_events(60):
                watch.process_events()

    @utils.exit_on_unhandled
    def _on_created(self, path):
        """This is the handler function when new files are seen"""
        if not os.path.exists(path):
            return

        localpath = os.path.basename(path)
        if localpath.startswith('.'):
            return

        _LOGGER.info('New event file - %r', path)

        when, instanceid, event_type, event_data = localpath.split(',', 4)
        with io.open(path) as f:
            payload = f.read()
        _publish_zk(
            self.zkclient, when, instanceid, event_type, event_data, payload
        )
        os.unlink(path)
