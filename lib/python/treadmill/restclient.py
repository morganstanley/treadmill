"""REST Client that uses requests library and defaults to SPNEGO auth.

This is meant to replace treadmill.http, as this uses outdated urlib.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import re
import time

import requests
import requests_unixsocket
import requests_kerberos
import simplejson.scanner

from six.moves import http_client

# to support unixscoket for URL
requests_unixsocket.monkeypatch()

_NUM_OF_RETRIES = 5

_KERBEROS_AUTH_PRINCIPLE = None
if os.name == 'posix':
    # kerberos 1.2.5 doesn't accept None principal. Remove this once fixed.
    _KERBEROS_AUTH_PRINCIPLE = ''

_KERBEROS_AUTH = requests_kerberos.HTTPKerberosAuth(
    mutual_authentication=requests_kerberos.DISABLED,
    principal=_KERBEROS_AUTH_PRINCIPLE
)

_LOGGER = logging.getLogger(__name__)

_DEFAULT_REQUEST_TIMEOUT = 10

_DEFAULT_CONNECT_TIMEOUT = .5

_CONNECTION_ERROR_STATUS_CODE = 599


def _msg(response):
    """Get response error message."""
    try:
        return response.json().get('message')
    except simplejson.scanner.JSONDecodeError:
        return response.text
    except Exception:  # pylint: disable=W0703
        return 'Unexpected error.'


class NoApiEndpointsError(Exception):
    """Error raised if list of api endpoints is empty."""


class HttpExceptionWithResponse(Exception):
    """Any error raised by an HTTP request

    Attributes:
    message -- message to return
    response - the response from the server
    """
    def __init__(self, response):
        super(HttpExceptionWithResponse, self).__init__(_msg(response))
        self.response = response


class NotAuthorizedError(HttpExceptionWithResponse):
    """Error raised on HTTP 401 (Unauthorized)"""


class BadRequestError(HttpExceptionWithResponse):
    """Error raised on HTTP 400 (Bad request)"""


class ValidationError(HttpExceptionWithResponse):
    """Error raised on HTTP 424 (Failed Dependency)."""


class NotFoundError(Exception):
    """Error raised on HTTP 404 (Not Found).

    Attributes:
    message -- message to return
    """


class AlreadyExistsError(Exception):
    """Error raised on HTTP 302 (Found).

    Attributes:
    message -- message to return
    """


class MaxRequestRetriesError(Exception):
    """Error raised when retry attempts are exceeded.

    Rest client will retry 5xx errors.

    Attributes:
    message -- message to return
    """
    def __init__(self, attempts):
        self.attempts = attempts
        super(MaxRequestRetriesError, self).__init__(
            'Retry count exceeded.')


def _handle_error(url, response):
    """Handle response status codes."""
    handlers = {
        http_client.NOT_FOUND: NotFoundError(
            'Resource not found: {}'.format(url)
        ),
        http_client.FOUND: AlreadyExistsError(
            'Resource already exists: {}'.format(url)
        ),
        http_client.FAILED_DEPENDENCY: ValidationError(response),
        http_client.UNAUTHORIZED: NotAuthorizedError(response),
        http_client.BAD_REQUEST: BadRequestError(response),
    }

    if response.status_code in handlers:
        raise handlers[response.status_code]


def _call(url, method, payload=None, headers=None, auth=_KERBEROS_AUTH,
          proxies=None, timeout=None, stream=None):
    """Call REST url with the supplied method and optional payload"""
    _LOGGER.debug('http: %s %s, payload: %s, headers: %s, timeout: %s',
                  method, url, payload, headers, timeout)

    try:
        response = getattr(requests, method.lower())(
            url, json=payload, auth=auth, proxies=proxies, headers=headers,
            timeout=timeout, stream=stream
        )
        _LOGGER.debug('response: %r', response)
    except requests.exceptions.ConnectionError:
        _LOGGER.debug('Connection error: %r', url)
        return False, None, _CONNECTION_ERROR_STATUS_CODE
    except requests.exceptions.Timeout:
        _LOGGER.debug('Request timeout: %r', timeout)
        return False, None, http_client.REQUEST_TIMEOUT

    if response.status_code == http_client.OK:
        return True, response, http_client.OK

    # Raise an appropirate exception for certain status codes (and never retry)
    _handle_error(url, response)

    # Everything else can be retried, just as connection error and req. timeout
    return False, response, response.status_code


def _call_list(urls, method, payload=None, headers=None, auth=_KERBEROS_AUTH,
               proxies=None, timeout=None, stream=None):
    """Call list of supplied URLs, return on first success."""
    _LOGGER.debug('Call %s on %r', method, urls)
    attempts = []
    for url in urls:
        success, response, status_code = _call(url, method, payload, headers,
                                               auth, proxies, timeout=timeout,
                                               stream=stream)
        if success:
            return success, response

        attempts.append((time.time(), url, status_code, _msg(response)))
    return False, attempts


def _call_list_with_retry(urls, method, payload, headers, auth, proxies,
                          retries, timeout=None, stream=None):
    """Call list of supplied URLs with retry."""
    if timeout is None:
        if method == 'get':
            timeout = _DEFAULT_REQUEST_TIMEOUT
        else:
            timeout = None

    retry = 0
    attempts = []
    while True:
        success, response = _call_list(
            urls, method, payload, headers, auth, proxies,
            timeout=(_DEFAULT_CONNECT_TIMEOUT + retry, timeout),
            stream=stream
        )
        if success:
            return response

        retry += 1
        attempts.extend(response)
        if retry >= retries:
            raise MaxRequestRetriesError(attempts)

        time.sleep(1)


def call(api, url, method, payload=None, headers=None, auth=_KERBEROS_AUTH,
         proxies=None, retries=_NUM_OF_RETRIES, timeout=None, stream=None):
    """Call url(s) with retry."""
    if not api:
        raise NoApiEndpointsError()

    if not isinstance(api, list):
        api = [api]

    return _call_list_with_retry(
        [endpoint + url for endpoint in api],
        method, payload, headers, auth, proxies, retries, timeout=timeout,
        stream=stream)


def get(api, url, headers=None, auth=_KERBEROS_AUTH, proxies=None,
        retries=_NUM_OF_RETRIES, timeout=None, stream=None):
    """Convenience function to get a resoure"""
    return call(api, url, 'get',
                headers=headers, auth=auth, proxies=proxies, retries=retries,
                timeout=timeout, stream=stream)


def post(api, url, payload, headers=None, auth=_KERBEROS_AUTH, proxies=None,
         retries=_NUM_OF_RETRIES, timeout=None):
    """Convenience function to create or POST a new resoure to url"""
    return call(api, url, 'post', payload=payload,
                headers=headers, auth=auth, proxies=proxies, retries=retries,
                timeout=timeout)


def delete(api, url, payload=None, headers=None, auth=_KERBEROS_AUTH,
           proxies=None, retries=_NUM_OF_RETRIES, timeout=None):
    """Convenience function to delete a resoure"""
    return call(api, url, 'delete', payload=payload,
                headers=headers, auth=auth, proxies=proxies, retries=retries,
                timeout=timeout)


def put(api, url, payload, headers=None, auth=_KERBEROS_AUTH, proxies=None,
        retries=_NUM_OF_RETRIES, timeout=None):
    """Convenience function to update a resoure"""
    return call(api, url, 'put', payload=payload,
                headers=headers, auth=auth, proxies=proxies, retries=retries,
                timeout=timeout)


def configure(api, url, payload, headers=None, auth=_KERBEROS_AUTH,
              proxies=None, retries=_NUM_OF_RETRIES, timeout=None):
    """Create or update resource."""
    try:
        return put(api, url, payload, headers, auth, proxies, retries,
                   timeout)
    except NotFoundError:
        return post(api, url, payload, headers, auth, proxies, retries,
                    timeout)


def handle_not_authorized(err):
    """Handle REST NotAuthorizedExceptions"""
    msg = str(err)
    msgs = [re.sub(r'failure: ', '    ', line) for line in msg.split(r'\n')]
    print('Not authorized: ', '\n'.join(msgs))


CLI_REST_EXCEPTIONS = [
    (NotFoundError, 'Resource not found'),
    (AlreadyExistsError, 'Resource already exists'),
    (ValidationError, None),
    (NotAuthorizedError, handle_not_authorized),
    (BadRequestError, None),
    (MaxRequestRetriesError, None)
]
