"""Wrapper for useful krb5 functions.

from treadmill.syscall import krb5
...
realms = krb5.get_host_realm(hostname)

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import ctypes

from ctypes import (
    c_int,
    c_void_p,
    c_char_p,
    byref,
    POINTER
)

from ctypes.util import find_library


_LOGGER = logging.getLogger(__name__)

try:
    _GSSAPI_PATH = find_library('gssapi_krb5')
    _GSSAPI = ctypes.CDLL(_GSSAPI_PATH, use_errno=True)
except Exception:  # pylint: disable=W0703
    _GSSAPI = None


def _load(decl, fname):
    """Safely load GSSAPI funciton."""
    if not _GSSAPI:
        return None

    try:
        return decl((fname, _GSSAPI))
    except AttributeError:
        return None


# Function declarations.
_CHAR_PP = POINTER(c_char_p)

_KRB5_INIT_CONTEXT_DECL = ctypes.CFUNCTYPE(
    c_int,
    POINTER(c_void_p),
    use_errno=True
)

_KRB5_FREE_CONTEXT_DECL = ctypes.CFUNCTYPE(
    c_int,
    c_void_p,
    use_errno=True
)

_KRB5_GET_HOST_REALM_DECL = ctypes.CFUNCTYPE(
    c_int,
    c_void_p,
    c_char_p,
    POINTER(_CHAR_PP),
    use_errno=True
)

_KRB5_FREE_HOST_REALM_DECL = ctypes.CFUNCTYPE(
    c_int,
    c_void_p,
    _CHAR_PP
)

_KRB5_INIT_CONTEXT = _load(
    _KRB5_INIT_CONTEXT_DECL,
    'krb5_init_context'
)

_KRB5_FREE_CONTEXT = _load(
    _KRB5_FREE_CONTEXT_DECL,
    'krb5_free_context'
)

_KRB5_GET_HOST_REALM = _load(
    _KRB5_GET_HOST_REALM_DECL,
    'krb5_get_host_realm'
)

_KRB5_FREE_HOST_REALM = _load(
    _KRB5_FREE_HOST_REALM_DECL,
    'krb5_free_host_realm',
)


def _check_funcs():
    """Check that all functions are loaded."""
    if _KRB5_INIT_CONTEXT is None:
        return False
    if _KRB5_FREE_CONTEXT is None:
        return False
    if _KRB5_GET_HOST_REALM is None:
        return False
    if _KRB5_FREE_HOST_REALM is None:
        return False

    return True


def get_host_realm(hostname):
    """Return list of kerberos realms given hostname.

    If Kerberos libraries cannot be loaded, return None.
    """
    if not _check_funcs():
        _LOGGER.debug(
            'krb5_ functions are not loaded: gssapi_krb5_%s', _GSSAPI
        )
        return None

    # krb5_error_code retval = 0;
    # krb5_context kcontext;
    #
    # retval = krb5_init_context(&kcontext);
    kcontext = c_void_p()
    krb5_error_code = _KRB5_INIT_CONTEXT(byref(kcontext))
    if krb5_error_code != 0:
        _LOGGER.debug('krb5_init_context failed, rc = %d', krb5_error_code)
        return None

    # char **realm_list = NULL;
    # retval = krb5_get_host_realm(kcontext, hostname, &realm_list);
    realm_list = _CHAR_PP()
    krb5_error_code = _KRB5_GET_HOST_REALM(
        kcontext,
        hostname.encode('utf-8'),
        byref(realm_list)
    )

    if krb5_error_code != 0:
        _LOGGER.debug('krb5_get_host_realm failed, rc = %d', krb5_error_code)
        _KRB5_FREE_CONTEXT(kcontext)
        return None

    try:
        realms = []
        idx = 0
        while True:
            realm = realm_list[idx]
            if not realm:
                break

            realms.append(realm.decode())
            idx = idx + 1

        return realms
    finally:
        # krb5_free_host_realm(kcontext, realm_list);
        # krb5_free_context(kcontext)
        krb5_error_code = _KRB5_FREE_HOST_REALM(kcontext, realm_list)
        krb5_error_code = _KRB5_FREE_CONTEXT(kcontext)


__all__ = [
    'get_host_realm',
]
