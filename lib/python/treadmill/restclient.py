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
import requests_kerberos
import simplejson.scanner

from six.moves import http_client

from treadmill import restclientopts

if os.name == "posix":
    # to support unixsocket for URL
    import requests_unixsocket 	# pylint: disable=import-error
    requests_unixsocket.monkeypatch()

_NUM_OF_RETRIES = 5

_LOGGER = logging.getLogger(__name__)

_DEFAULT_REQUEST_TIMEOUT = 10

_DEFAULT_CONNECT_TIMEOUT = .5

_CONNECTION_ERROR_STATUS_CODE = 599

_DEBUG_TXT_LEN = 120


def _krb_auth():
    """Returns kerberos auth object."""
    auth_principle = None
    if os.name == 'posix':
        # kerberos 1.2.5 doesn't accept None principal. Remove this once fixed.
        auth_principle = ''

    return requests_kerberos.HTTPKerberosAuth(
        mutual_authentication=requests_kerberos.DISABLED,
        principal=auth_principle,
        service=restclientopts.AUTH_PRINCIPAL
    )


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
    """Error raised on HTTP 403 (FORBIDDEN)"""


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
    """Error raised on HTTP 409 (Conflict).

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
        # XXX: Correct code is CONFLICT. Support invalid FOUND during
        #      migration.
        http_client.FOUND: AlreadyExistsError(
            'Resource already exists: {}'.format(url)
        ),
        http_client.CONFLICT: AlreadyExistsError(
            'Resource already exists: {}'.format(url)
        ),
        http_client.FAILED_DEPENDENCY: ValidationError(response),
        # XXX: Correct code is FORBIDDEN. Support invalid UNAUTHORIZED during
        #      migration.
        http_client.UNAUTHORIZED: NotAuthorizedError(response),
        http_client.FORBIDDEN: NotAuthorizedError(response),
        http_client.BAD_REQUEST: BadRequestError(response),
    }

    if response.status_code in handlers:
        raise handlers[response.status_code]


def _is_info(status_code):
    """Check if status code is informational: 100 <= 200"""
    return 100 <= status_code < 200


def _is_success(status_code):
    """Check if status code is success."""
    return 200 <= status_code < 300


def _is_redirect(status_code):
    """Check if status code is redirect."""
    return 300 <= status_code < 400


def _is_client_error(status_code):
    """Check if status code is client error."""
    return 400 <= status_code < 500


def _is_server_error(status_code):
    """Check if status code is server error."""
    return status_code >= 500


def _call(url, method, payload=None, headers=None, auth=None,
          proxies=None, timeout=None, stream=None, verify=True,
          payload_to_json=True, allow_redirects=True):
    """Call REST url with the supplied method and optional payload"""
    _LOGGER.debug('http: %s %s, payload: %s, headers: %s, timeout: %s',
                  method, url, payload, headers, timeout)

    if auth is None:
        auth = _krb_auth()

    method_kwargs = dict(auth=auth, proxies=proxies, headers=headers,
                         timeout=timeout, stream=stream, verify=verify,
                         allow_redirects=allow_redirects)

    method_kwargs['json' if payload_to_json else 'data'] = payload

    try:
        # pylint: disable=not-callable
        response = getattr(requests, method.lower())(url, **method_kwargs)
        _LOGGER.debug(
            'Response[%d] - %s',
            response.status_code,
            (response.content if len(response.content) <= _DEBUG_TXT_LEN
             else '{}...'.format(response.content[:_DEBUG_TXT_LEN]))
        )
    except requests.exceptions.ConnectionError:
        _LOGGER.debug('Connection error: %r', url)
        return False, None, _CONNECTION_ERROR_STATUS_CODE
    except requests.exceptions.Timeout:
        _LOGGER.debug('Request timeout: %r', timeout)
        return False, None, http_client.REQUEST_TIMEOUT

    if _is_success(response.status_code) or _is_info(response.status_code):
        return True, response, response.status_code

    if _is_client_error(response.status_code):
        _handle_error(url, response)
        # if above line does not raise, return response and do not retry.
        return True, response, response.status_code

    # Server errors will be retried:
    if _is_server_error(response.status_code):
        return False, response, response.status_code

    # Everything else can be retried, just as connection error and req. timeout
    return False, response, response.status_code


def _call_list(urls, method, payload=None, headers=None, auth=None,
               proxies=None, timeout=None, stream=None, verify=True,
               payload_to_json=True, allow_redirects=True):
    """Call list of supplied URLs, return on first success."""
    _LOGGER.debug('Call %s on %r', method, urls)
    attempts = []
    for url in urls:
        success, response, status_code = _call(
            url, method, payload, headers, auth, proxies, timeout=timeout,
            stream=stream, verify=verify,
            payload_to_json=payload_to_json,
            allow_redirects=allow_redirects,
        )
        if success:
            return success, response

        attempts.append((time.time(), url, status_code, _msg(response)))
    return False, attempts


def _call_list_with_retry(urls, method, payload, headers, auth, proxies,
                          retries, timeout=None, stream=None, verify=True,
                          payload_to_json=True, allow_redirects=True):
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
            stream=stream, verify=verify,
            payload_to_json=payload_to_json,
            allow_redirects=allow_redirects,
        )
        if success:
            return response

        retry += 1
        attempts.extend(response)
        if retry >= retries:
            raise MaxRequestRetriesError(attempts)

        time.sleep(1)


def call(api, url, method, payload=None, headers=None, auth=None,
         proxies=None, retries=_NUM_OF_RETRIES, timeout=None, stream=None,
         verify=True, payload_to_json=True, allow_redirects=True):
    """Call url(s) with retry."""
    if not api:
        raise NoApiEndpointsError()

    if not isinstance(api, list):
        api = [api]

    return _call_list_with_retry(
        [endpoint + url for endpoint in api],
        method, payload, headers, auth, proxies, retries, timeout=timeout,
        stream=stream, verify=verify,
        payload_to_json=payload_to_json,
        allow_redirects=allow_redirects)


def get(api, url, headers=None, auth=None, proxies=None,
        retries=_NUM_OF_RETRIES, timeout=None, stream=None, verify=True,
        allow_redirects=True):
    """Convenience function to get a resoure"""
    return call(api, url, 'get',
                headers=headers, auth=auth, proxies=proxies, retries=retries,
                timeout=timeout, stream=stream, verify=verify,
                allow_redirects=allow_redirects)


def post(api, url, payload, headers=None, auth=None, proxies=None,
         retries=_NUM_OF_RETRIES, timeout=None, verify=True,
         payload_to_json=True, allow_redirects=True):
    """Convenience function to create or POST a new resoure to url"""
    return call(api, url, 'post', payload=payload,
                headers=headers, auth=auth, proxies=proxies, retries=retries,
                timeout=timeout, verify=verify,
                payload_to_json=payload_to_json,
                allow_redirects=allow_redirects)


def delete(api, url, payload=None, headers=None, auth=None,
           proxies=None, retries=_NUM_OF_RETRIES, timeout=None, verify=True,
           payload_to_json=True, allow_redirects=True):
    """Convenience function to delete a resoure"""
    return call(api, url, 'delete', payload=payload,
                headers=headers, auth=auth, proxies=proxies, retries=retries,
                timeout=timeout, verify=verify,
                payload_to_json=payload_to_json,
                allow_redirects=allow_redirects)


def put(api, url, payload, headers=None, auth=None, proxies=None,
        retries=_NUM_OF_RETRIES, timeout=None, verify=True,
        payload_to_json=True, allow_redirects=True):
    """Convenience function to update a resoure"""
    return call(api, url, 'put', payload=payload,
                headers=headers, auth=auth, proxies=proxies, retries=retries,
                timeout=timeout, verify=verify,
                payload_to_json=payload_to_json,
                allow_redirects=allow_redirects)


def configure(api, url, payload, headers=None, auth=None,
              proxies=None, retries=_NUM_OF_RETRIES, timeout=None,
              verify=True, payload_to_json=True):
    """Create or update resource."""
    try:
        return put(api, url, payload, headers, auth, proxies, retries,
                   timeout, verify, payload_to_json)
    except NotFoundError:
        return post(api, url, payload, headers, auth, proxies, retries,
                    timeout, verify, payload_to_json)


def handle_not_authorized(err):
    """Handle REST NotAuthorizedExceptions"""
    msg = str(err)
    msgs = [re.sub(r'failure: ', '    ', line) for line in msg.split(r'\n')]
    print('Not authorized: {}'.format(','.join(msgs)))


CLI_REST_EXCEPTIONS = [
    (NotFoundError, 'Resource not found'),
    (AlreadyExistsError, 'Resource already exists'),
    (ValidationError, None),
    (NotAuthorizedError, handle_not_authorized),
    (BadRequestError, None),
    (MaxRequestRetriesError, None)
]
