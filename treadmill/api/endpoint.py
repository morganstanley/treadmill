"""Implementation of endpoint API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import fnmatch
import kazoo

from treadmill import context
from treadmill import utils
from treadmill import zknamespace as z


_LOGGER = logging.getLogger(__name__)


def make_endpoint_watcher(zkclient, state, proid):
    """Make endpoint watcher function."""
    proid_instances = z.join_zookeeper_path(z.ENDPOINTS, proid)

    @zkclient.ChildrenWatch(proid_instances)
    @utils.exit_on_unhandled
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
                endpoints[name] = data.decode()
            except kazoo.client.NoNodeError:
                pass

        state[proid].update(endpoints)
        return True

    return _watch_instances


class API(object):
    """Treadmill Endpoint REST api."""

    def __init__(self):

        cell_state = dict()

        if context.GLOBAL.cell is not None:
            zkclient = context.GLOBAL.zk.conn

            @zkclient.ChildrenWatch(z.ENDPOINTS)
            @utils.exit_on_unhandled
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
