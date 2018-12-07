"""Implementation of endpoint API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import fnmatch

import kazoo
import six

from treadmill import context
from treadmill import utils
from treadmill import yamlwrapper as yaml
from treadmill import zknamespace as z
from treadmill import zkwatchers


_LOGGER = logging.getLogger(__name__)


def make_endpoint_watcher(zkclient, state, proid):
    """Make endpoint watcher function."""
    proid_instances = z.join_zookeeper_path(z.ENDPOINTS, proid)

    @zkclient.ChildrenWatch(proid_instances)
    @utils.exit_on_unhandled
    def _watch_instances(children):
        """Watch for proid instances."""

        # TODO: current implementation does nto support instances, so
        #       state from masters will be stored, but will be never displayed.
        current = set(state[proid].keys())
        target = set(children)

        for name in current - target:
            del state[proid][name]

        endpoints = dict()
        for name in target - current:
            try:
                endpoint_node = z.join_zookeeper_path(proid_instances, name)
                data, _metadata = zkclient.get(endpoint_node)
                endpoints[name] = data.decode()
            except kazoo.client.NoNodeError:
                pass

        state[proid].update(endpoints)
        return True

    return _watch_instances


def make_discovery_state_watcher(zkclient, state, server):
    """Watch server state changes."""

    discovery_state_node = z.path.discovery_state(server)

    @zkwatchers.ExistingDataWatch(zkclient, discovery_state_node)
    @utils.exit_on_unhandled
    def _watch_discovery_state(data, _stat, event):
        """Watch discovery state for given server."""
        if (data is None or
                (event is not None and event.type == 'DELETED')):
            # The node is deleted
            state.pop(server, None)
            return False
        else:
            # Reestablish the watch.
            # TODO: need to remember change it to json once zkutils is modified
            #       to store json rather than yaml.
            state[server] = yaml.load(data)
            return True


class API:
    """Treadmill Endpoint REST api."""

    def __init__(self):

        cell_state = {}
        ports_state = {}

        if context.GLOBAL.cell is not None:
            zkclient = context.GLOBAL.zk.conn

            @zkclient.ChildrenWatch(z.ENDPOINTS)
            @utils.exit_on_unhandled
            def _watch_endpoints(proids):
                """Watch /endpoints nodes."""

                current = set(cell_state.keys())
                target = set(proids)

                for proid in current - target:
                    _LOGGER.info('Removing proid: %s', proid)
                    cell_state.pop(proid, None)

                for proid in target - current:
                    _LOGGER.info('Adding proid: %s', proid)
                    cell_state[proid] = {}
                    make_endpoint_watcher(zkclient, cell_state, proid)

                return True

            @zkclient.ChildrenWatch(z.DISCOVERY_STATE)
            @utils.exit_on_unhandled
            def _watch_discovery_state(servers):
                """Watch discovery state."""
                current = set(ports_state.keys())
                target = set(servers)

                for server in current - target:
                    _LOGGER.info('Removing server state: %s', server)
                    ports_state.pop(server, None)

                for server in target - current:
                    _LOGGER.info('Adding server state: %s', server)
                    ports_state[server] = {}
                    make_discovery_state_watcher(zkclient, ports_state, server)

                return True

        def _list(pattern, proto, endpoint):
            """List endpoints state."""
            _LOGGER.info('list: %s %s %s', pattern, proto, endpoint)

            proid, match = pattern.split('.', 1)

            match = match or '*'
            if '#' not in match:
                match += '#*'

            if endpoint is None:
                endpoint = '*'

            if proto is None:
                proto = '*'

            _LOGGER.debug('match: %r, proto: %r, endpoint: %r',
                          match, proto, endpoint)
            full_pattern = ':'.join([match, proto, endpoint])

            endpoints = cell_state.get(proid, {})
            _LOGGER.debug('endpoints: %r', endpoints)

            filtered = []
            for name, hostport in six.viewitems(endpoints.copy()):
                if not fnmatch.fnmatch(name, full_pattern):
                    continue
                appname, proto, endpoint = name.split(':')
                host, port = hostport.split(':')
                port = int(port)
                try:
                    state = bool(ports_state[host][port])
                except KeyError:
                    _LOGGER.exception('not found: %s:%d', host, port)
                    state = None

                filtered.append({'name': proid + '.' + appname,
                                 'proto': proto,
                                 'endpoint': endpoint,
                                 'host': host,
                                 'port': port,
                                 'state': state})

            return sorted(filtered, key=lambda item: item['name'])

        self.list = _list
