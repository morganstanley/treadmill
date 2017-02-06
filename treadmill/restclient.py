"""REST Client that uses requests library and defaults to SPNEGO auth.

This is meant to replace treadmill.http, as this uses outdated urlib.
"""


import http.client
import logging
import time

import requests
import requests_kerberos
import simplejson.scanner


_NUM_OF_RETRIES = 5

_KERBEROS_AUTH = requests_kerberos.HTTPKerberosAuth(
    mutual_authentication=requests_kerberos.DISABLED
)

_LOGGER = logging.getLogger(__name__)

_DEFAULT_REQUEST_TIMEOUT = 10

_DEFAULT_CONNECT_TIMEOUT = .5


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
    def __init__(self, msg):
        super(NotFoundError, self).__init__(msg)


class AlreadyExistsError(Exception):
    """Error raised on HTTP 302 (Found).

    Attributes:
    message -- message to return
    """
    def __init__(self, msg):
        super(AlreadyExistsError, self).__init__(msg)


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
        http.client.NOT_FOUND: NotFoundError('Resource not found: %s' % url),
        http.client.FOUND: AlreadyExistsError(
            'Resource already exists: %s' % url
        ),
        http.client.FAILED_DEPENDENCY: ValidationError(response),
        http.client.UNAUTHORIZED: NotAuthorizedError(response),
        http.client.BAD_REQUEST: BadRequestError(response),
    }

    if response.status_code in handlers:
        raise handlers[response.status_code]


def _should_retry(response):
    """Check if response should retry."""
    return response.status_code in [http.client.INTERNAL_SERVER_ERROR,
                                    http.client.BAD_GATEWAY,
                                    http.client.SERVICE_UNAVAILABLE]


def _call(url, method, payload=None, headers=None, auth=_KERBEROS_AUTH,
          proxies=None, timeout=None):
    """Call REST url with the supplied method and optional payload"""
    _LOGGER.debug('http: %s %s, payload: %s, headers: %s, timeout: %s',
                  method, url, payload, headers, timeout)

    try:
        response = getattr(requests, method.lower())(
            url, json=payload, auth=auth, proxies=proxies, headers=headers,
            timeout=timeout
        )
        _LOGGER.debug('response: %r', response)
    except requests.exceptions.Timeout:
        _LOGGER.debug('Request timeout: %r', timeout)
        return False, None, http.client.REQUEST_TIMEOUT

    if response.status_code == http.client.OK:
        return True, response, http.client.OK

    if _should_retry(response):
        _LOGGER.debug('Retry: %s', response.status_code)
        return False, response, response.status_code

    _handle_error(url, response)
    return False, response, response.status_code


def _call_list(urls, method, payload=None, headers=None, auth=_KERBEROS_AUTH,
               proxies=None, timeout=None):
    """Call list of supplied URLs, return on first success."""
    _LOGGER.debug('Call %s on %r', method, urls)
    attempts = []
    for url in urls:
        success, response, status_code = _call(url, method, payload, headers,
                                               auth, proxies, timeout=timeout)
        if success:
            return success, response

        attempts.append((time.time(), url, status_code, _msg(response)))
    return False, attempts


def _call_list_with_retry(urls, method, payload, headers, auth, proxies,
                          retries, timeout=None):
    """Call list of supplied URLs with retry."""
    attempts = []
    if timeout is None:
        timeout = _DEFAULT_REQUEST_TIMEOUT

    attempt = 0
    while True:
        success, response = _call_list(
            urls, method, payload, headers, auth, proxies,
            timeout=(_DEFAULT_CONNECT_TIMEOUT + attempt, timeout)
        )
        if success:
            return response

        attempts.extend(response)
        if len(attempts) > retries:
            raise MaxRequestRetriesError(attempts)

        attempt += 1
        time.sleep(1)


def call(api, url, method, payload=None, headers=None, auth=_KERBEROS_AUTH,
         proxies=None, retries=_NUM_OF_RETRIES, timeout=None):
    """Call url(s) with retry."""
    if not api:
        raise NoApiEndpointsError()

    if not isinstance(api, list):
        api = [api]

    return _call_list_with_retry(
        [endpoint + url for endpoint in api],
        method, payload, headers, auth, proxies, retries, timeout=timeout)


def get(api, url, headers=None, auth=_KERBEROS_AUTH, proxies=None,
        retries=_NUM_OF_RETRIES, timeout=None):
    """Convenience function to get a resoure"""
    return call(api, url, 'get',
                headers=headers, auth=auth, proxies=proxies, retries=retries,
                timeout=timeout)


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
