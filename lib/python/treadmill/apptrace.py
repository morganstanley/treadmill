"""Watch for application state transitions."""

from __future__ import absolute_import

import fnmatch
import logging
import os
import time
import threading

import kazoo

from . import exc
from . import zknamespace as z


_LOGGER = logging.getLogger(__name__)


class AppTraceEvents(object):
    """Base class for processing events."""

    def on_task_scheduled(self, when, server):
        """Invoked when task is scheduled."""
        pass

    def on_task_pending(self, when):
        """Invoked when task is pending."""
        pass

    def on_task_deleted(self, when):
        """Invoked when task is deleted."""
        pass

    def on_task_finished(self, when, server):
        """Invoked when task is finished."""
        pass

    def on_task_killed(self, when, server, oom):
        """Default task-finished handler."""
        pass

    def on_task_aborted(self, when, server):
        """Invoked when task is aborted."""
        pass

    def on_service_running(self, when, server, service):
        """Invoked when service is running."""
        pass

    def on_service_exit(self, when, server, service, exitcode, signal):
        """Invoked when service exits."""
        pass


class AppTrace(object):
    """Trace application lifecycle events.

    Application events are stored under app task Zookeeper directory, sequence
    node for each event.

    events are in the form:
    timestamp,source,event,msg
    """

    def __init__(self, zkclient, appname, callback=None):
        self.zk = zkclient
        self.appname = appname
        self.last_event = None

        self.exit = False
        self.normal_exit = False
        self.app = None
        self.done = None

        # Store exit codes for the services.
        self.exitinfo = dict([('finished', False),
                              ('aborted', False),
                              ('scheduled', False),
                              ('running', False),
                              ('killed', False),
                              ('oom', False),
                              ('hostname', False),
                              ('exits', [])])

        if callback:
            self.callback = callback
        else:
            self.callback = AppTraceEvents()

    def set_event(self):
        """Safely sets event."""
        if self.done is not None:
            self.done.set()

    def run(self, snapshot=False, wait_scheduled=False):
        """Process application events."""
        # pylint complains too many branches.
        #
        # pylint: disable=R0912
        if not snapshot:
            self.done = threading.Event()

        scheduled_node = z.path.scheduled(self.appname)

        @self.zk.DataWatch(scheduled_node)
        @exc.exit_on_unhandled
        def _watch_scheduled(data, stat, event):
            """Called when app scheduled node is modified."""
            if event and event.type == 'DELETED':
                self.exitinfo['scheduled'] = False
                self.set_event()
                return False

            if data is None and stat is None:
                # Node does not exist (gone) or deleted.
                self.exitinfo['scheduled'] = False
                if not wait_scheduled:
                    self.set_event()
                    return False
                else:
                    return not snapshot
            else:
                self.exitinfo['scheduled'] = True
                return not snapshot

        running_node = z.path.running(self.appname)

        @self.zk.DataWatch(running_node)
        @exc.exit_on_unhandled
        def _watch_running(data, stat, _event):
            """Called when app running node is modified."""
            if data is None and stat is None:
                # Node does not exist (gone) or deleted.
                self.exitinfo['running'] = False
                self.exitinfo['hostname'] = None
            else:
                self.exitinfo['running'] = True
                self.exitinfo['hostname'] = data

            return not snapshot and self.exitinfo['scheduled']

        task_node = z.path.task(self.appname)

        @self.zk.DataWatch(task_node)
        @exc.exit_on_unhandled
        def _watch_task(data, stat, event):
            """Watch for task to appear and then process events."""
            # If task not is deleted, this is fatal, and we should exit.
            if event and event.type == 'DELETED':
                self.exitinfo['error'] = 'task deleted.'
                return False

            if data is not None and stat is not None:
                if 'error' in self.exitinfo:
                    del self.exitinfo['error']

                @self.zk.ChildrenWatch(task_node, send_event=True)
                @exc.exit_on_unhandled
                def _watch_task_events(event_nodes, event):
                    """Process new events."""
                    if event and event.type == 'DELETED':
                        return False

                    self.process_events(event_nodes)
                    return not snapshot

                return False
            else:
                self.exitinfo['error'] = 'task does not exist.'
                return not snapshot

    def process_events(self, event_nodes):
        """Process event nodes."""
        all_events = sorted([tuple(event_node.split(','))
                             for event_node in event_nodes])

        for timestamp, source, event, msg in all_events:
            if timestamp < self.last_event:
                continue

            self.process_event(timestamp, source, event, msg)
            self.last_event = timestamp

    def process_event(self, timestamp, source, event, msg):
        """Process event of given type."""
        # Master events.
        when = float(timestamp)
        if event == 'scheduled':
            _LOGGER.info('%s - task scheduled on: %s', when, msg)
            self.callback.on_task_scheduled(when, msg)
        elif event == 'pending':
            _LOGGER.info('%s - task pending.', when)
            self.callback.on_task_pending(when)
        elif event == 'deleted':
            _LOGGER.info('%s - task deleted.', when)
            self.callback.on_task_deleted(when)

        # Node events.
        elif event == 'killed':
            oom = msg == 'oom'
            if msg == 'oom':
                _LOGGER.info('%s - %s: task killed, out of memory.',
                             when, source)
            else:
                _LOGGER.info('%s - %s: task killed.',
                             when, source)
            self.callback.on_task_killed(when, source, oom=oom)
        elif event == 'finished':
            _LOGGER.info('%s - %s: task finished.', when, source)
            self.callback.on_task_finished(when, source)

        # Service events.
        elif event == 'running':
            _LOGGER.info('%s - %s: %s is running.', when, source, msg)
            self.callback.on_service_running(when, source, msg)
        elif event == 'exit':
            service, exitcode, signal = msg.rsplit('.', 3)
            _LOGGER.info('%s - %s: %s exited rc = %s, signal = %s',
                         when, source, service, exitcode, signal)
            self.callback.on_service_exit(when, source, service,
                                          exitcode=exitcode, signal=signal)
        else:
            _LOGGER.info('%s - %s: %s - %s', when, source, event, msg)

    def wait(self, timeout=None):
        """Wait for app lifecycle to finish.

        Returns True if event loop is finished, False otherwise (timeout).
        """
        # Wait event was never initialized, was used for snapshot.
        if self.done is None:
            return True

        self.done.wait(timeout)
        return self.done.isSet()


def cleanup(zkclient, expire_after, max_events=1024):
    """Iterates over tasks nodes and deletes all that are expired."""
    # Enumerate all tasks.
    tasks = set(zkclient.get_children('/tasks'))
    scheduled = set(zkclient.get_children('/scheduled'))

    for task in tasks:
        task_node = os.path.join('/tasks', task)
        instances = set(zkclient.get_children(task_node))

        # Filter out instances that are not running
        finished = set([instance for instance in instances
                        if '#'.join([task, instance]) not in scheduled])

        for instance in instances:
            instance_node = os.path.join(task_node, instance)
            _LOGGER.info('Processing task: %s/%s', task_node, instance)
            events = sorted([tuple(reversed(node.rsplit('-', 1)))
                             for node in zkclient.get_children(instance_node)])
            # Maintain at most N events
            if len(events) > max_events:
                extra = len(events) - max_events
                _LOGGER.info('Deleting extra events for node: %s %s',
                             instance_node, extra)

                for event in events[:extra]:
                    ev_node = '-'.join(reversed(event))
                    ev_fullpath = os.path.join(task_node, instance, ev_node)

                    zkclient.delete(ev_fullpath)

            if instance in finished:
                # Check last event time stamp, and it if is > expired, mark
                # the whole node as expired.
                expired = False
                if not events:
                    expired = True
                else:
                    last_ev_node = '-'.join(reversed(events[-1]))
                    last_ev_fullpath = os.path.join(task_node,
                                                    instance,
                                                    last_ev_node)
                    _data, metadata = zkclient.get(last_ev_fullpath)
                    if metadata.last_modified + expire_after < time.time():
                        _LOGGER.info('Instance %s expired.', instance)
                        expired = True

                # If xpired, delete all events and then delete the task node.
                if expired:
                    _LOGGER.info('Deleting instance node: %s', instance_node)
                    zkclient.delete(instance_node, recursive=True)

        try:
            zkclient.delete('/tasks/' + task)
            _LOGGER.info('/tasks/%s empty, deleting.', task)
        except kazoo.exceptions.NotEmptyError:
            _LOGGER.info('/tasks/%s not empty.', task)


def list_history(zkclient, app_pattern):
    """List all historical tasks for given app name."""
    tasks = []
    for app in zkclient.get_children('/tasks'):
        if fnmatch.fnmatch(app, app_pattern):
            instances = zkclient.get_children(os.path.join('/tasks', app))
            tasks.extend([app + '#' + instance for instance in instances])

    return tasks
