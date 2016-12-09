"""REST Client that uses requests library and defaults to SPNEGO auth.

This is meant to replace treadmill.http, as this uses outdated urlib.
"""
from __future__ import absolute_import

import httplib
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


class NotAuthorizedError(Exception):
    """Error raised on HTTP 401 (Unauthorized)

    Attributes:
    message -- message to return
    """
    def __init__(self, response):
        super(NotAuthorizedError, self).__init__(_msg(response))


class BadRequestError(Exception):
    """Error raised on HTTP 400 (Bad request)

    Attributes:
    message -- message to return
    """
    def __init__(self, response):
        super(BadRequestError, self).__init__(_msg(response))


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


class ValidationError(Exception):
    """Error raised on HTTP 424 (Failed Dependency).

    Attributes:
    message -- message to return
    """
    def __init__(self, response):
        super(ValidationError, self).__init__(_msg(response))


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
        httplib.NOT_FOUND: NotFoundError('Resource not found: %s' % url),
        httplib.FOUND: AlreadyExistsError('Resource already exists: %s' % url),
        httplib.FAILED_DEPENDENCY: ValidationError(response),
        httplib.UNAUTHORIZED: NotAuthorizedError(response),
        httplib.BAD_REQUEST: BadRequestError(response),
    }

    if response.status_code in handlers:
        raise handlers[response.status_code]


def _should_retry(response):
    """Check if response should retry."""
    return response.status_code in [httplib.INTERNAL_SERVER_ERROR,
                                    httplib.BAD_GATEWAY,
                                    httplib.SERVICE_UNAVAILABLE]


def _call(url, method, payload=None, headers=None, auth=_KERBEROS_AUTH,
          proxies=None):
    """Call REST url with the supplied method and optional payload"""
    _LOGGER.debug('http: %s %s, payload: %s, headers: %s',
                  method, url, payload, headers)

    response = getattr(requests, method.lower())(
        url, json=payload, auth=auth, proxies=proxies, headers=headers
    )
    _LOGGER.debug('response: %r', response)

    if response.status_code == httplib.OK:
        if callable(getattr(response, 'json')):
            _LOGGER.debug('response.json: %r', response.json())

        return True, response

    if _should_retry(response):
        _LOGGER.debug('Retry: %s', response.status_code)
        return False, response

    _handle_error(url, response)
    return False, response


def _call_list(urls, method, payload=None, headers=None, auth=_KERBEROS_AUTH,
               proxies=None):
    """Call list of supplied URLs, return on first success."""
    _LOGGER.debug('Call %s on %r', method, urls)
    attempts = []
    for url in urls:
        success, response = _call(url, method, payload, headers, auth, proxies)
        if success:
            return success, response

        attempts.append((time.time(), url,
                         response.status_code, _msg(response)))
    return False, attempts


def _call_list_with_retry(urls, method, payload, headers, auth, proxies,
                          retries):
    """Call list of supplied URLs with retry."""
    attempts = []
    for _attempt in xrange(0, retries):
        success, response = _call_list(
            urls, method, payload, headers, auth, proxies)
        if success:
            return response

        attempts.extend(response)
        time.sleep(1)

    raise MaxRequestRetriesError(attempts)


def call(api, url, method, payload=None, headers=None, auth=_KERBEROS_AUTH,
         proxies=None, retries=_NUM_OF_RETRIES):
    """Call url(s) with retry."""
    if not api:
        raise NoApiEndpointsError()

    if not isinstance(api, list):
        api = [api]

    return _call_list_with_retry(
        [endpoint + url for endpoint in api],
        method, payload, headers, auth, proxies, retries)


def get(api, url, headers=None, auth=_KERBEROS_AUTH, proxies=None,
        retries=_NUM_OF_RETRIES):
    """Convenience function to get a resoure"""
    return call(api, url, 'get',
                headers=headers, auth=auth, proxies=proxies, retries=retries)


def post(api, url, payload, headers=None, auth=_KERBEROS_AUTH, proxies=None,
         retries=_NUM_OF_RETRIES):
    """Convenience function to create or POST a new resoure to url"""
    return call(api, url, 'post', payload=payload,
                headers=headers, auth=auth, proxies=proxies, retries=retries)


def delete(api, url, payload=None, headers=None, auth=_KERBEROS_AUTH,
           proxies=None, retries=_NUM_OF_RETRIES):
    """Convenience function to delete a resoure"""
    return call(api, url, 'delete', payload=payload,
                headers=headers, auth=auth, proxies=proxies, retries=retries)


def put(api, url, payload, headers=None, auth=_KERBEROS_AUTH, proxies=None,
        retries=_NUM_OF_RETRIES):
    """Convenience function to update a resoure"""
    return call(api, url, 'put', payload=payload,
                headers=headers, auth=auth, proxies=proxies, retries=retries)
