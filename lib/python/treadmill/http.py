"""Helper module to perform HTTP requests with SPNEGO auth."""

from __future__ import absolute_import

import json
import urllib2
import urllib2_kerberos


def create_http_opener(proxy=None):
    """Creates http opener with spnego handler."""
    # This is to clear proxy support
    https_support = urllib2.HTTPSHandler(debuglevel=1)

    if not proxy:
        proxy = {}

    if proxy == 'ENV':
        proxy_support = urllib2.ProxyHandler()
    else:
        proxy_support = urllib2.ProxyHandler(proxy)

    krb_support = urllib2_kerberos.HTTPKerberosAuthHandler(mutual=False)
    return urllib2.build_opener(https_support, proxy_support, krb_support)


def make_request(url, method, data, headers=None):
    """Constructs http request."""
    request = urllib2.Request(url)

    # pylint complains about lambda not being necessary.
    request.get_method = lambda: method.upper()  # pylint: disable=W0108
    if request.get_method() not in ['GET', 'DELETE']:
        if data is None:
            length = 0
        else:
            if not isinstance(data, str):
                payload = json.dumps(data)
            else:
                payload = data

            length = len(payload)
            request.add_data(payload)

        request.add_header('Content-Length', str(length))

    # Add the headers (list of (k, v) tuples)
    if not headers:
        headers = []

    for header in headers:
        if len(header) == 2:
            key, value = header
            key.strip(' ')
            value.strip(' ')
        else:
            key = header[0]
            key.strip(' ')
            value = '1'

        request.add_header(key, value)

    return request
