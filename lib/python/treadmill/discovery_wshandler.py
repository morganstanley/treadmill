"""
A WebSocket handler for Treadmill's discovery
"""

from __future__ import absolute_import

import os

import json
import logging
import traceback

from treadmill import exc
from treadmill import discovery
from treadmill import utils
from treadmill import websocket
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)


class DiscoveryWebSocketHandler(websocket.WebSocketHandlerBase):
    """Application discovery WebSocket Handler"""

    def __init__(self, application, request, **kwargs):
        """Default constructor for websocket.WebSocketHandlerBase"""

        _LOGGER.info('Initializing treadmill.discovery_wshandler.'
                     'DiscoveryWSHandler')
        websocket.WebSocketHandlerBase.__init__(self, application, request,
                                                **kwargs)
        # Default attributes
        self.deltas = False
        self.cell = None
        self.pattern = None
        self.endpoint = None
        # internal attributes
        self.endpoints = None

    def on_message(self, jmessage):
        """This method is called per client, for every message received.

            :param: jmessage
                This is a json message from the client and can contain the
                following keys:

                    - cell: cell name to discover endpoint information;
                      required
                    - pattern: a pattern name to filter output, e.g.
                      "test1/ericktr.foo"; this is required
                    - endpoint: the name of a specific endpoint
                    - deltas: option to only send deltas, not a full image
                      of the state, i.e. only applications that have been added

            Example return objects:

            SOW: {"endpoints": [{"name": "treadmlp.discovery#0000076619:ws",
            "hostport": "zzz.xxx.com:60755"}, {"name":
            "treadmlp.discovery#0000077140:http", "hostport":
            "zzz.xxx.com:56107"}], "sow": true}

            Deltas: {"deleted": ["test1/user1.foo#0000002936"], "state":
            "running", "sow": false}
        """
        try:
            message = json.loads(jmessage)
            _LOGGER.debug('message: %s', message)

            self.set_attributes(message)

            _LOGGER.info('Sending endpoints SOW for %s/%s back to the client',
                         self.cell, self.pattern)
            self.send_current_endpoints(True)

            path = self.get_node_path()

            _LOGGER.info('Watching children under path: %s', path)
            self.zkclient.get_children(path, self.endpoint_watcher)

        except:  # pylint: disable=W0702
            err = traceback.format_exc().splitlines()
            self.send_error_msg('Unexpected error processing message: %s' %
                                err[-1])

    def get_node_path(self):
        """Return the node path for endpoints"""
        return os.path.join(zkutils.ENDPOINTS, self.pattern.split('.', 1)[0])

    def endpoint_watcher(self, event):
        """Watches changes to event.path

        When we get in here, get the current 'endpoints' for all children,
        then return the full state back to the client, unless they want deltas
        only, then calculate the dealtas and provide the action that was
        taken with the differences.
        """
        try:
            _LOGGER.debug('event: %r', event)

            previous_endpoints = self.endpoints or {}
            _LOGGER.debug('previous_endpoints: %s', previous_endpoints)

            current_endpoints = self.get_current_endpoints(False)
            _LOGGER.debug('current_endpoints: %r', current_endpoints)

            _LOGGER.info('Overriding previous state info to the current one')
            self.endpoints = current_endpoints

            # We short-circuit if we don't want deltas
            if not self.deltas:
                _LOGGER.info('Deltas is not set, returning current state...')
                current_endpoints['sow'] = True
                self.write_message(json.dumps(current_endpoints))
            else:
                _LOGGER.info('Client is only interested in the deltas,'
                             ' returning the difference between current'
                             ' state and previous state')

                self.send_deltas(previous_endpoints,
                                 current_endpoints)

            _LOGGER.info('Sit watching children under path: %s', event.path)
            self.zkclient.get_children(event.path, self.endpoint_watcher)
        except:  # pylint: disable=W0702
            err = traceback.format_exc().splitlines()
            self.send_error_msg('Unexpected error while watching path %s: %s' %
                                (event.path, err[-1]))

    def send_deltas(self, previous, current):
        """Get deltas between current and previous endpoints"""

        previous_apps = self.get_instance_set(previous)
        current_apps = self.get_instance_set(current)

        response = {'sow': False}

        deleted = self.get_endpoints_by_instances(
            previous, list(previous_apps - current_apps))
        response[websocket.DeltaActions.DELETED.value] = deleted

        created = self.get_endpoints_by_instances(
            current, list(current_apps - previous_apps))
        response[websocket.DeltaActions.CREATED.value] = created

        _LOGGER.debug('response: %r', response)

        if (response[websocket.DeltaActions.DELETED.value] or
                response[websocket.DeltaActions.CREATED.value]):
            _LOGGER.info('Sending deltas back to the client')
            self.write_message(json.dumps(response))
        else:
            _LOGGER.info('No differences found, thus not sending'
                         ' anything back.')

    def get_instance_set(self, endpoints):
        """Get instance names as a set from an array of dict's"""
        if endpoints is None or not endpoints.get('endpoints'):
            return set([])

        instances = set([ep['name'] for ep in endpoints['endpoints']])
        _LOGGER.debug('instances: %r', instances)

        return instances

    def get_endpoints_by_instances(self, endpoints, instances):
        """Get endpoints by the instance names"""
        _LOGGER.debug('endpoints: %r', endpoints)

        return [ep for ep in endpoints['endpoints'] if ep['name'] in instances]

    def set_attributes(self, message):
        """Helper function to set all this objects attributes from message"""
        schema = [
            ('cell', True, unicode),
            ('pattern', True, unicode),
            ('endpoint', False, unicode),
            ('deltas', False, bool),
        ]
        try:
            utils.validate(message, schema)
        except exc.InvalidInputError, err:
            self.send_error_msg('Invalid data: %s: %s' % (message, err))
            return

        self.cell = message.get('cell')
        _LOGGER.debug('cell: %s', self.cell)

        self.endpoint = message.get('endpoint')
        _LOGGER.debug('endpoint %s', self.endpoint)

        if not self.endpoint:
            self.endpoint = websocket.GLOB_CHAR

        self.pattern = message.get('pattern')

        # Note: required, as the validate method does:
        # struct[field] = ftype()
        # Which I believe is wrong, why are we doing autovivication?
        if not self.pattern:
            self.pattern = None

        if (self.pattern is not None and not
                self.pattern.endswith(websocket.GLOB_CHAR)):
            self.pattern = self.pattern + websocket.GLOB_CHAR
        _LOGGER.debug('pattern: %r', self.pattern)

        self.deltas = message.get('deltas', False)
        _LOGGER.debug('deltas: %r', self.deltas)

    def get_current_endpoints(self, is_sow=False):
        """This method will get the current endpoints.

            Based on the cell, pattern, and endpoint that the client sent in
            the on_message, this method will return a list of dictionaries.

            :param is_sow
                Whether this state is "SOW" (i.e. State Of the World) or not;
                default is False
        """

        _LOGGER.info('Discovering endpoints in %r with pattern %s',
                     self.cell, self.pattern)

        app_discovery = discovery.Discovery(self.zkclient, self.pattern,
                                            self.endpoint)

        endpoint_nodes = app_discovery.get_endpoints_zk()
        _LOGGER.debug('endpoint_nodes: %r', endpoint_nodes)

        endpoints = [{'name': '.'.join([app_discovery.prefix, endpoint]),
                      'hostport': app_discovery.resolve_endpoint(endpoint)}
                     for endpoint in endpoint_nodes]

        discovered = {'sow': is_sow, 'endpoints': endpoints}

        return discovered

    def send_current_endpoints(self, is_sow=False):
        """
        Send the current endpoints with any pattern filtering
        """

        discovered = self.get_current_endpoints(is_sow)
        _LOGGER.debug('discovered: %r', discovered)

        self.endpoints = discovered

        _LOGGER.info('Sending current endpoints back to client...')
        self.write_message(json.dumps(discovered))
        _LOGGER.info('Finished sending current endpoints back to client')
