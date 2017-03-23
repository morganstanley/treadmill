"""Implementation of endpoint API."""


import logging

import fnmatch
import kazoo

from .. import context
from .. import exc
from .. import zknamespace as z


_LOGGER = logging.getLogger(__name__)


def make_endpoint_watcher(zkclient, state, proid):
    """Make endpoint watcher function."""
    proid_instances = z.join_zookeeper_path(z.ENDPOINTS, proid)

    @exc.exit_on_unhandled
    @zkclient.ChildrenWatch(proid_instances)
    def _watch_instances(children):
        """Watch for proid instances."""

        current = set(state[proid].keys())
        target = set(children)

        for name in current - target:
            del state[proid][name]

        endpoints = dict()
        for name in target - current:
            try:
                endpoint_node = z.join_zookeeper_path(proid_instances, name)
                data, _metadata = zkclient.get(endpoint_node)
                endpoints[name] = data
            except kazoo.client.NoNodeError:
                pass

        state[proid].update(endpoints)
        return True

    return _watch_instances


class API(object):
    """Treadmill endpoint REST api."""

    def __init__(self):

        zkclient = context.GLOBAL.zk.conn

        cell_state = dict()

        @exc.exit_on_unhandled
        @zkclient.ChildrenWatch(z.ENDPOINTS)
        def _watch_endpoints(proids):
            """Watch /endpoints nodes."""

            current = set(cell_state.keys())
            target = set(proids)

            for proid in current - target:
                del cell_state[proid]

            for proid in target - current:
                if proid not in cell_state:
                    cell_state[proid] = {}
                make_endpoint_watcher(zkclient, cell_state, proid)

            return True

        def _list(pattern, proto, endpoint):
            """List endpoints state."""
            proid, match = pattern.split('.', 1)

            if not match:
                match = '*'
            if match.find('#') == -1:
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
            for name, hostport in endpoints.items():
                if not fnmatch.fnmatch(name, full_pattern):
                    continue
                appname, proto, endpoint = name.split(':')
                host, port = hostport.split(':')
                filtered.append({'name': proid + '.' + appname,
                                 'proto': proto,
                                 'endpoint': endpoint,
                                 'host': host,
                                 'port': port})

            return sorted(filtered, key=lambda item: item['name'])

        self.list = _list


def init(_authorizer):
    """Returns module API wrapped with authorizer function."""
    return API()
