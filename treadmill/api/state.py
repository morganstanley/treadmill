"""Implementation of state API."""


import logging

import fnmatch
import yaml

from .. import context
from .. import schema
from .. import exc
from .. import zknamespace as z


_LOGGER = logging.getLogger(__name__)


class API(object):
    """Treadmill State REST api."""

    def __init__(self):

        zkclient = context.GLOBAL.zk.conn

        cell_state = {
            'running': [],
            'placement': {}
        }

        @exc.exit_on_unhandled
        @zkclient.ChildrenWatch(z.path.running())
        def _watch_running(running):
            """Watch /running nodes."""
            cell_state['running'] = set(running)
            for name, item in cell_state.get('placement', {}).items():
                state = item['state'] = (
                    'running' if name in cell_state['running'] else 'scheduled'
                )
                if item['host'] is not None:
                    item['state'] = state
            return True

        @exc.exit_on_unhandled
        @zkclient.DataWatch(z.path.placement())
        def _watch_placement(placement, _stat, event):
            """Watch /placement data."""
            if placement is None or event == 'DELETED':
                cell_state['placement'] = {}
                return True

            updated_placement = {}
            for row in yaml.load(placement):
                instance, _before, _exp_before, after, expires = tuple(row)
                if after is None:
                    state = 'pending'
                else:
                    state = 'scheduled'
                    if instance in cell_state.get('running', set()):
                        state = 'running'
                updated_placement[instance] = {
                    'state': state,
                    'host': after,
                    'expires': expires,
                }
            cell_state['placement'] = updated_placement
            return True

        def _list(match):
            """List instances state."""
            if match is None:
                match = '*'
            if '#' not in match:
                match += '#*'
            filtered = [
                {'name': name, 'state': item['state'], 'host': item['host']}
                for name, item in cell_state.get('placement', {}).items()
                if fnmatch.fnmatch(name, match)
            ]
            return sorted(filtered, key=lambda item: item['name'])

        @schema.schema({'$ref': 'instance.json#/resource_id'})
        def get(rsrc_id):
            """Get instance state."""
            data = cell_state['placement'].get(rsrc_id)
            if data:
                data.update({'name': rsrc_id})
            return data

        self.list = _list
        self.get = get


def init(_authorizer):
    """Returns module API wrapped with authorizer function."""
    # There is no authorization for state api.
    return API()
