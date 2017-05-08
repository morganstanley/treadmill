"""Helper module to perform HTTP requests with SPNEGO auth."""

import json
import urllib.request
import urllib.error
import urllib.parse
import urllib_kerberos


def create_http_opener(proxy=None):
    """Creates http opener with spnego handler."""
    # This is to clear proxy support
    https_support = urllib.request.HTTPSHandler(debuglevel=1)

    if not proxy:
        proxy = {}

    if proxy == 'ENV':
        proxy_support = urllib.request.ProxyHandler()
    else:
        proxy_support = urllib.request.ProxyHandler(proxy)

    krb_support = urllib_kerberos.HTTPKerberosAuthHandler(mutual=False)
    return urllib.request.build_opener(
        https_support, proxy_support, krb_support
    )


def make_request(url, method, data, headers=None):
    """Constructs http request."""
    request = urllib.request.Request(url)

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
            request.data = payload

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
