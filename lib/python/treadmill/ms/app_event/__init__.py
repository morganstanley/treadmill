"""Syncronize event to WatchTower.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import heapq
import io
import logging
import os
import sqlite3

from treadmill import dirwatch
from treadmill import exc
from treadmill import utils
from treadmill import yamlwrapper as yaml
from treadmill import apptrace
from treadmill.apptrace import events

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms.watchtower import api as wtapi
from treadmill.ms.app_event import engine as app_event_engine

_LOGGER = logging.getLogger(__name__)

FACET = 'CONTAINER'

# FIXME: SQLite code duplicated from treadmill.websocket.


class EventEmitter(object):
    """Delivery Event"""

    def __init__(self, cell, fs_root, host, port, since):
        self.cell = cell
        self._fs_root = os.path.realpath(fs_root)
        self._client = None
        self._since = since
        self._event_root = os.path.join(self._fs_root, 'trace')
        self._appgroup_root = os.path.join(self._fs_root, 'app-groups')
        self._sow_root = os.path.join(self._fs_root, apptrace.TRACE_SOW_DIR)
        self._sow_db_table = apptrace.TRACE_SOW_TABLE

        self.watcher = dirwatch.DirWatcher()
        self.watcher.on_created = self._on_created
        self.watcher.on_deleted = self._on_deleted
        self.watcher.on_modified = self._on_modified

        self._sender = wtapi.EventSender(cell, FACET, host=host, port=port)
        self._engines = (app_event_engine.ExitEventEngine(self._sender),
                         app_event_engine.PendingEventEngine(self._sender),)

    def _register(self):
        """ register should be called in the start """
        pattern = os.path.join(self._event_root, '*')

        watch_dirs = self._get_watch_dirs(pattern)
        for directory in watch_dirs:
            self.watcher.add_dir(directory)

        self.watcher.add_dir(self._appgroup_root)

    def _match_appgroup(self, app_group_file):
        """For all apps that match the appgroup, add to target state."""

        try:
            with io.open(app_group_file) as f:
                app_group = yaml.load(stream=f)

        except IOError:
            _LOGGER.info('Appgroup deleted: %s', app_group_file)
            return None

        if app_group['group-type'] != 'event':
            return None

        data = utils.equals_list2dict(app_group.get('data'))
        _LOGGER.debug('data: %r', data)

        pending = data.get('pending')
        exits = data.get('exit')
        if not pending and not exits:
            _LOGGER.error('No valid event definition for %r',
                          app_group)
            return None

        if pending:
            pending = int(pending)

        if exits:
            exits = tuple(exits.split(','))

        return (app_group['pattern'], exits, pending)

    def _load_target_apps(self):
        """Returns target app groups as defined by zk mirror on file system."""
        appgroups_pattern = os.path.join(self._appgroup_root, '*')
        for app_group_f in glob.glob(appgroups_pattern):
            if os.path.basename(app_group_f).startswith('.'):
                continue

            _LOGGER.debug('app_group file: %r', app_group_f)
            self._configure_app_group(app_group_f)

    def _configure_app_group(self, path):
        """ for app group file is created or modified """
        app_group_def = self._match_appgroup(path)

        if app_group_def is None:
            return

        app_group_name = self._app_group_name(path)
        for engine in self._engines:
            engine.add_policy(app_group_name, app_group_def)

    def _delete_app_group(self, path):
        """ delete app group if app group file is deleted """
        app_group_name = self._app_group_name(path)

        for engine in self._engines:
            engine.del_policy(app_group_name)

    def _process_app_event(self, event, path=None):
        """ deal with app event from data """

        for engine in self._engines:
            engine.process(event, path)

    def _process_app_event_file(self, path):
        """ deal with app event from file name """
        event = os.path.basename(path)
        event_obj = self._create_event(event)
        if event_obj is None:
            return

        if event_obj.timestamp < self._since:
            return

        self._process_app_event(event_obj, path)

    def _db_records(self, db_path, sow_table, since):
        """Get matching records from db."""
        _LOGGER.info('Using sow db: %s, sow table: %s, since %d',
                     db_path, sow_table, since)
        conn = sqlite3.connect(db_path)

        # Before Python 3.7 GLOB pattern must not be parametrized to use index.
        select_stmt = """
            SELECT timestamp, name, data FROM %s
            WHERE timestamp >= ?
            ORDER BY timestamp
        """ % sow_table

        # Return open connection, as conn.execute is cursor iterator, not
        # materialized list.
        def _event_generator():
            for (_when, name, content) in conn.execute(select_stmt, (since,)):
                event = self._create_event(name, content)
                if event is not None:
                    yield (_when, event, None)

        return conn, _event_generator()

    def _get_fs_sow(self, since):
        """ get fs sow data that has not been archived into sow sqlite db """
        fs_events = []

        pattern = os.path.join(self._event_root, '*')
        watch_dirs = self._get_watch_dirs(pattern)
        for directory in watch_dirs:
            for event in os.listdir(directory):
                if event.startswith('.'):
                    continue

                event_file = os.path.join(directory, event)
                event = self._create_event(event)
                # if event is not coverted, we ignore it
                if event is None:
                    continue

                if event.timestamp < since:
                    continue

                fs_events.append((event.timestamp, event, event_file))

        return sorted(fs_events, key=lambda x: x[0])

    def _sow(self, since):
        """ Get sow data """

        fs_records = self._get_fs_sow(since)

        db_connections = []
        try:
            records = []
            dbs = sorted(glob.glob(os.path.join(self._sow_root, '*')))
            for db in dbs:
                if os.path.basename(db).startswith('.'):
                    continue

                conn, db_cursor = self._db_records(
                    db, self._sow_db_table, since
                )
                records.append(db_cursor)
                # FIXME: Figure out pylint use before assign
                db_connections.append(conn)  # pylint: disable=E0601

            records.append(fs_records)

            prev_event = None
            for item in heapq.merge(*records):
                (_when, event, path) = item
                if event == prev_event:
                    continue
                prev_event = event
                self._process_app_event(event, path)
        finally:
            for conn in db_connections:
                if conn:
                    conn.close()

        # mark engine ready to send event
        for engine in self._engines:
            engine.ready()

    @utils.exit_on_unhandled
    def _on_created(self, path):
        """On file created callback."""
        _LOGGER.debug('created: %s', path)

        if path.startswith(self._appgroup_root):
            self._configure_app_group(path)

        if path.startswith(self._event_root):
            self._process_app_event_file(path)

    @utils.exit_on_unhandled
    def _on_modified(self, path):
        """On file modified callback."""
        _LOGGER.debug('modified: %s', path)

        if path.startswith(self._appgroup_root):
            self._configure_app_group(path)

        # we are not interested in event file modification

    @utils.exit_on_unhandled
    def _on_deleted(self, path):
        """On file deleted callback."""
        _LOGGER.debug('deleted: %s', path)

        if path.startswith(self._appgroup_root):
            self._delete_app_group(path)

    @utils.exit_on_unhandled
    def run(self, once=False):
        """ run event emitter """
        # load all effective app groups in the beginning
        self._load_target_apps()

        # register dir watcher handler
        self._register()

        # first run try to send sow data
        _LOGGER.info(
            'send all matchting historical events after %d', self._since
        )
        self._sow(self._since)

        wait_interval = 10
        while True:
            if once:
                wait_interval = 0

            self._sender.dispatch()

            if self.watcher.wait_for_events(wait_interval):
                self.watcher.process_events()

            if once:
                break

    @staticmethod
    def _create_event(event, content=None):
        (instanceid,
         timestamp,
         src_host,
         event_type,
         event_data) = event.split(',', 4)

        try:
            return events.AppTraceEvent.from_data(
                timestamp=float(timestamp),
                source=src_host,
                instanceid=instanceid,
                event_type=event_type,
                event_data=event_data,
                payload=content
            )
        # yes, we need to catch any exception to generate event
        # pylint: disable=W0703
        except Exception as err:
            _LOGGER.error('unable to create trace event %s: %r', event, err)
            return None

    @staticmethod
    def _get_watch_dirs(watch_dir):
        """ because trace dir has shards """
        pathname = os.path.realpath(watch_dir)
        return [path for path in glob.glob(pathname) if os.path.isdir(path)]

    @staticmethod
    def _app_group_name(app_group_file):
        return os.path.basename(app_group_file)
