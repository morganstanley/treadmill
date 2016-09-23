"""
A WebSocket handler for Treadmill state's, e.g. 'running',
'scheduled', or 'configured'
"""
from __future__ import absolute_import

import json
import logging
import traceback

from treadmill import exc
from treadmill import state
from treadmill import utils
from treadmill import websocket


_LOGGER = logging.getLogger(__name__)


class StateWebSocketHandler(websocket.WebSocketHandlerBase):
    """Application state WebSocket Handler"""

    def __init__(self, application, request, **kwargs):
        """Default constructor for websocket.WebSocketHandlerBase"""

        _LOGGER.info('Initialized treadmill.state_wshandler.StateWSHandler...')
        websocket.WebSocketHandlerBase.__init__(self, application, request,
                                                **kwargs)
        # Default attributes
        self.deltas = False
        self.cell = None
        self.app = None
        self.pattern = None
        self.state = None
        self.state_info = None

    def state_watcher(self, event):
        """
        Watches changes to event.path, when we get in here, get the current
        'state' for all children, then return the full state back to the
        client, unless they want deltas only, then calculate the dealtas and
        provide the action that was taken with the differences.
        """
        try:
            _LOGGER.debug('event: %r', event)

            previous_state_info = self.state_info
            _LOGGER.debug('previous_state_info: %s', previous_state_info)

            current_state_info = self.get_current_state(False)
            _LOGGER.debug('current_state_info: %r', current_state_info)

            # We short-circuit if we don't want deltas
            if not self.deltas:
                _LOGGER.info('Deltas is not set, returning current state...')
                current_state_info['sow'] = True
                self.write_message(json.dumps(current_state_info))
            else:
                _LOGGER.info('Client is only interested in the deltas,'
                             ' returning the difference between current'
                             ' state and previous state')
                previous_apps = set(previous_state_info[self.state])
                current_apps = set(current_state_info[self.state])

                response = {'sow': False, }

                response[websocket.DeltaActions.DELETED.value] = list(
                    previous_apps - current_apps)

                response[websocket.DeltaActions.CREATED.value] = list(
                    current_apps - previous_apps)

                response['state'] = self.state
                _LOGGER.debug('response: %r', response)

                if (response[websocket.DeltaActions.DELETED.value] or
                        response[websocket.DeltaActions.CREATED.value]):
                    self.write_message(json.dumps(response))
                else:
                    _LOGGER.info('No differences found, thus not sending'
                                 ' anything back.')

            _LOGGER.info('Overriding previous state info to the current one')
            self.state_info = current_state_info

            _LOGGER.info('Sit watching children under path: %s', event.path)
            self.zkclient.get_children(event.path, self.state_watcher)
        except:  # pylint: disable=W0702
            err = traceback.format_exc().splitlines()
            self.send_error_msg('Unexpected error while watching path %s: %s' %
                                (event.path, err[-1]), close_conn=False)
            _LOGGER.info('Sit watching children under path: %s', event.path)
            self.zkclient.get_children(event.path, self.state_watcher)

    def watch_children(self, path):
        """Get SOW, send to client then setup a watcher on path"""

        # Send SOW of current state
        _LOGGER.info('Sending SOW for state "%s" back to the client...',
                     self.state)
        self.state_info = self.get_current_state(True)
        _LOGGER.debug('state_info: %r', self.state_info)

        self.write_message(json.dumps(self.state_info))

        _LOGGER.info('Sit watching children under path: %s', path)
        self.zkclient.get_children(path, self.state_watcher)

    def on_message(self, jmessage):
        """
        This method is called every time we receive a message from the
        client.

        :param jmessage:
            This is a json message from the client and can contain the
            following keys:

            - cell: cell name to get state information; required
            - state: the state state name to retrieve apps for;
                     this is required, possible values are state.STATES
            - pattern: a pattern name to filter output, e.g.
                       "test1/ericktr.foo"
            - deltas: option to only send deltas, not a full image
                      of the state, i.e. only applications that have been added

            Example return objects::

             SOW: {"running": ["test1/ericktr.foo#0000000595",
                               "test1/ericktr.foo#0000002937"],
                   "sow": true}
             Deltas: {"deleted": ["test1/ericktr.foo#0000002936"],
                      "state": "running",
                      "sow": false}

        :type jmessage:
            ``str``
        """
        try:
            _LOGGER.debug('jmessage: %s', jmessage)
            message = json.loads(jmessage)
            _LOGGER.debug('message: %s', message)

            self.set_attributes(message)

            if self.zkclient is None:
                self.send_error_msg('Could not get zookeeper connection to'
                                    ' cell "%s"' % self.state)
                return

            if self.state not in state.STATE_NODE_MAP:
                self.send_error_msg('The supplied state "%s" is not known' %
                                    self.state)
                return

            node_path = state.STATE_NODE_MAP.get(self.state)

            if node_path is None:
                self.send_error_msg('The supplied state "%s" is not supported'
                                    % self.state)
                return

            self.watch_children(node_path)

        except Exception as ex:  # pylint: disable=W0702,W0703
            _LOGGER.exception(ex)
            err = traceback.format_exc().splitlines()
            self.send_error_msg('Unexpected error processing message: %s' %
                                err[-1])

    def set_attributes(self, message):
        """Helper function to set all this objects attributes from message"""
        schema = [
            ('cell', True, unicode),
            ('state', True, unicode),
            ('app', False, unicode),
            ('pattern', False, unicode),
            ('deltas', False, bool),
        ]
        try:
            utils.validate(message, schema)
        except exc.InvalidInputError, err:
            self.send_error_msg('Invalid data: %s: %s' % (message, err))
            return

        self.cell = message.get('cell')
        _LOGGER.debug('cell: %s', self.cell)

        self.state = message.get('state')
        _LOGGER.debug('state: %s', self.state)

        # Further validation of the state
        if self.state not in state.STATE_NODE_MAP:
            self.send_error_msg('The supplied state "%s" is not valid',
                                self.state)
            return

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

        self.app = message.get('app')

        # Note: same as above
        if not self.app:
            self.app = None
        _LOGGER.debug('app: %r', self.app)

        if self.app is not None:
            self.app = self.app + websocket.GLOB_CHAR

        if self.app is None and self.pattern is None:
            self.send_error_msg('You must supply at least a pattern or an app'
                                ' key as part of the request')
            return

        self.deltas = message.get('deltas', False)
        _LOGGER.debug('deltas: %r', self.deltas)

    def get_current_state(self, is_sow=False):
        """
            This method will send the current state to the client, based on the
            cell, pattern, and state that the client sent in the on_message.

            :param is_sow
                Whether this state is "SOW" (i.e. State Of the World) or not;
                default is False
        """

        _LOGGER.info('Getting state in: %r', self.cell)
        state_lister = state.State(self.cell, self.zkclient)

        state_info = {'sow': is_sow}
        state_info[self.state] = []

        pattern = self.pattern
        if pattern is None:
            pattern = self.app

        _LOGGER.info('Listing apps in %r with pattern %s',
                     self.state, pattern)
        apps = state_lister.list(self.state, pattern)

        if apps is None:
            return state_info

        if isinstance(apps, dict):
            apps = apps.items()

        _LOGGER.debug('apps: %r', apps)

        state_info[self.state] = apps

        return state_info

    def send_current_state(self, is_sow=False):
        """
        Send the current state with any pattern filtering
        """

        state_info = self.get_current_state(is_sow)
        _LOGGER.debug('state_info: %r', state_info)

        _LOGGER.info('Sending current state back to client...')
        self.write_message(json.dumps(state_info))
        _LOGGER.info('Finished sending current state back to client')
