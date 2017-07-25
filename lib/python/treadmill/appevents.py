"""Process application events."""
from __future__ import absolute_import

import tempfile
import logging
import os
import time

import kazoo.client

from treadmill import exc
from treadmill import dirwatch
from treadmill import sysinfo
from treadmill import zkutils
from treadmill import zknamespace as z
from treadmill import yamlwrapper as yaml


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
            zkclient.create,
            z.path.trace(instanceid, eventnode),
            payload,
            acl=[_SERVERS_ACL],
            makepath=True
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

        scheduled_node = z.path.scheduled(instanceid)
        _LOGGER.info('Unscheduling, event=%s: %s', event_type, scheduled_node)
        zkutils.with_retry(
            zkutils.ensure_deleted, zkclient,
            scheduled_node
        )


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
    if not isinstance(payload, str):
        payload = yaml.dump(payload)
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
    with tempfile.NamedTemporaryFile(dir=events_dir,
                                     delete=False,
                                     prefix='.tmp') as temp:
        if isinstance(payload, str):
            temp.write(payload)
        else:
            yaml.dump(payload, stream=temp)
    os.rename(temp.name, os.path.join(events_dir, filename))


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

    @exc.exit_on_unhandled
    def _on_created(self, path):
        """This is the handler function when new files are seen"""
        if not os.path.exists(path):
            return

        localpath = os.path.basename(path)
        if localpath.startswith('.'):
            return

        _LOGGER.info('New event file - %r', path)

        when, instanceid, event_type, event_data = localpath.split(',', 4)
        with open(path) as f:
            payload = f.read()
        _publish_zk(
            self.zkclient, when, instanceid, event_type, event_data, payload
        )
        os.unlink(path)
