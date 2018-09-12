"""Websocket client implementation.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import logging
import socket
import time
import urllib

import websocket as ws_client


_LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30


class WSConnectionError(Exception):
    """Error raised when connection attempts fail."""


CLI_WS_EXCEPTIONS = [
    (WSConnectionError, 'Could not connect to the websocket API')
]


class _RetryError(Exception):
    """Error indicating that retry attempt should be made."""

    def __init__(self, since):
        Exception.__init__(self)
        self.since = since


def _ws_events(ws_conn, message, snapshot, since, on_message, on_error):
    """Process websocket events."""
    # Pylint complains too many nested blocks.
    #
    # pylint: disable=R0101
    last_timestamp = since
    subscription_msg = {'since': since,
                        'snapshot': snapshot}
    subscription_msg.update(message)

    try:
        ws_conn.send(json.dumps(subscription_msg))
        while True:
            try:
                reply = ws_conn.recv()
                if not reply:
                    break

                result = json.loads(reply)
                if '_error' in result:
                    if on_error:
                        on_error(result)
                    break

                last_timestamp = result.get('when', time.time())
                if on_message:
                    if not on_message(result):
                        break
            except ws_client.WebSocketTimeoutException:
                ws_conn.ping()

    except ws_client.WebSocketConnectionClosedException as err:
        _LOGGER.debug('ws connection closed, will retry: %s.', str(err))
        raise _RetryError(last_timestamp)
    finally:
        ws_conn.close()


def ws_loop(apis, message, snapshot, on_message, on_error=None,
            timeout=_DEFAULT_TIMEOUT):
    """Instance trace loop."""
    ws_conn = None
    since = 0

    while True:
        for api in apis:

            try:
                _LOGGER.debug('Connecting to %s, [timeout: %s]', api, timeout)
                parsed = urllib.parse.urlparse(api)
                if ':' in parsed.netloc:
                    host, _port = parsed.netloc.split(':')
                else:
                    host = parsed.netloc
                # TODO: we never use proxy when connecting to websocket
                #       server. It is not clear if such behavior need to be
                #       optional.
                #
                #       Need to set both http_proxy_host AND http_no_proxy.
                #       The code in websocket client only examines _no_proxy if
                #       http_proxy_host is set. If it is not, it ignores the
                #       no_proxy setting, and latter on initializes proxy from
                #       environment variables (BUG).
                ws_conn = ws_client.create_connection(
                    api,
                    timeout=timeout,
                    http_proxy_host='__ignored__.yet.must.be.set',
                    http_no_proxy=[host]
                )
                _LOGGER.debug('Connected.')

                _LOGGER.debug('Sending %s', json.dumps(message))
                return _ws_events(ws_conn, message, snapshot, since,
                                  on_message, on_error)
            except ws_client.WebSocketTimeoutException as to_err:
                _LOGGER.debug('Connection timeout: %s, %s', api, str(to_err))
                continue
            except ws_client.WebSocketProxyException as proxy_err:
                _LOGGER.debug('Websocket connection error: %s, %s', api,
                              str(proxy_err))
                continue
            except socket.error:
                _LOGGER.debug('Connection failed: %s', api)
                continue
            except _RetryError as retry_err:
                since = retry_err.since

        if not ws_conn:
            raise WSConnectionError()
