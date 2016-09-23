"""
Base websocket class to Tornado's webcoket.

This class overrides several methods including:

 - on_close: called when connection closed; right now this just logs the event
 - open: called when connection is opened; right now this just logs the event

This class will also provide the following methods:

 - get_zkclient: returns and caches ZK clients at the cell level
 - send_error_msg: utility method to help send back an error and close the
   connection to the client

"""
from __future__ import absolute_import

import datetime
import logging
import urlparse

from enum import Enum
import tornado.websocket

from . import context


_LOGGER = logging.getLogger(__name__)

GLOB_CHAR = '*'


class DeltaActions(Enum):
    # pylint: disable=W0232
    """
    Enum for the different Delta actions that can be returned to the client.
    """
    CREATED = 'created'
    DELETED = 'deleted'


class WebSocketHandlerBase(tornado.websocket.WebSocketHandler):
    """Base class contructor"""

    def __init__(self, application, request, **kwargs):
        """Default constructor for tornado.websocket.WebSocketHandler"""
        _LOGGER.info('Initializing treadmill.websocket.WebSocketHandlerBase')
        tornado.websocket.WebSocketHandler.__init__(self, application, request,
                                                    **kwargs)
        self.zkclient = context.GLOBAL.zk.conn

    def open(self):
        """Called when connection is opened.

        Override if you want to do something else besides log the action."""
        _LOGGER.info('A new connection has been opened...')

    def send_error_msg(self, error_str, close_conn=True):
        """This is a convenience method for logging and returning errors.

        Note: this method will close the connection after sending back the
        error, unless close_conn=False """
        _LOGGER.error(error_str)
        error_msg = {'_error': error_str,
                     'when': datetime.datetime.utcnow().isoformat()}

        self.write_message(error_msg)

        if close_conn:
            _LOGGER.warn('Closing connection to client...')
            self.close()

    def on_close(self):
        """Called when connection is closed.

        Override if you want to do something else besides log the action."""
        _LOGGER.warn('We are closing connection to client.')

    def check_origin(self, origin):
        """Overriding check_origin method from base class.

        This method returns true all the time"""
        parsed_origin = urlparse.urlparse(origin)
        _LOGGER.debug('parsed_origin: %r', parsed_origin)
        return True

    def on_message(self, message):
        """Override this method in your handler"""
        raise BaseException('You must override this method in your class')

    def data_received(self, message):
        """Passthrough of abstract method data_received"""
        pass
