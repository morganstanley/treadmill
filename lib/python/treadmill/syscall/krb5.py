"""Wrapper for useful krb5 functions.

from treadmill.syscall import krb5
...
realms = krb5.get_host_realm(hostname)

"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import logging
import platform
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


def _get_gssapi_path():
    if os.name == 'nt':
        if platform.architecture()[0] == '64bit':
            lib_name = 'krb5_64'
        else:
            lib_name = 'krb5_32'
    else:
        lib_name = 'gssapi_krb5'

    return find_library(lib_name)


try:
    _GSSAPI_PATH = _get_gssapi_path()
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

_KRB5_CC_RESOLVE_DECL = ctypes.CFUNCTYPE(
    c_int,
    c_void_p,
    c_char_p,
    POINTER(c_void_p),
)

_KRB5_CC_CLOSE_DECL = ctypes.CFUNCTYPE(
    c_int,
    c_void_p,
    c_void_p,
)

_KRB5_CC_GET_PRINCIPAL_DECL = ctypes.CFUNCTYPE(
    c_int,
    c_void_p,
    c_void_p,
    POINTER(c_void_p),
)

_KRB5_FREE_PRINCIPAL_DECL = ctypes.CFUNCTYPE(
    c_int,
    c_void_p,
    c_void_p,
)

_KRB5_UNPARSE_NAME_DECL = ctypes.CFUNCTYPE(
    c_int,
    c_void_p,
    c_void_p,
    POINTER(c_char_p),
)

_KRB5_FREE_UNPARSED_NAME_DECL = ctypes.CFUNCTYPE(
    c_int,
    c_void_p,
    c_char_p,
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

_KRB5_CC_RESOLVE = _load(
    _KRB5_CC_RESOLVE_DECL,
    'krb5_cc_resolve',
)

_KRB5_CC_CLOSE = _load(
    _KRB5_CC_CLOSE_DECL,
    'krb5_cc_close',
)

_KRB5_CC_GET_PRINCIPAL = _load(
    _KRB5_CC_GET_PRINCIPAL_DECL,
    'krb5_cc_get_principal',
)

_KRB5_FREE_PRINCIPAL = _load(
    _KRB5_FREE_PRINCIPAL_DECL,
    'krb5_free_principal',
)

_KRB5_UNPARSE_NAME = _load(
    _KRB5_UNPARSE_NAME_DECL,
    'krb5_unparse_name',
)

_KRB5_FREE_UNPARSED_NAME = _load(
    _KRB5_FREE_UNPARSED_NAME_DECL,
    'krb5_free_unparsed_name',
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


def get_principal(krb5ccname=None):
    """Return default principal in the credential cache."""
    # Disable too many return statements warning.
    # TODO: refactor code so that it is less "c" like, with better cleanup
    #       handling.
    #
    # pylint: disable=R0911
    if not _check_funcs():
        _LOGGER.debug(
            'krb5_ functions are not loaded: gssapi_krb5_%s', _GSSAPI
        )
        return None

    if krb5ccname is None:
        krb5ccname = os.environ.get('KRB5CCNAME')

    if not krb5ccname:
        return None

    cleanups = []
    try:
        # krb5_error_code retval = 0;
        # krb5_context kcontext;
        #
        # retval = krb5_init_context(&kcontext);
        kcontext = c_void_p()
        krb5_error_code = _KRB5_INIT_CONTEXT(byref(kcontext))
        if krb5_error_code != 0:
            _LOGGER.debug('krb5_init_context failed, rc = %d', krb5_error_code)
            return None

        cleanups.append(lambda: _KRB5_FREE_CONTEXT(kcontext))

        # krb5_ccache cache;
        # retval = krb5_cc_resolve(kcontext, (const char *)krb5ccname, &cache);
        cache = c_void_p()
        krb5_error_code = _KRB5_CC_RESOLVE(
            kcontext, krb5ccname.encode('utf8'), byref(cache)
        )
        if krb5_error_code != 0:
            _LOGGER.debug('krb5_cc_resolve failed, rc = %d', krb5_error_code)
            return None

        cleanups.append(lambda: _KRB5_CC_CLOSE(kcontext, cache))

        # krb5_principal princ;
        # retval = krb5_cc_get_principal(kcontext, cache, &princ);
        princ = c_void_p()
        krb5_error_code = _KRB5_CC_GET_PRINCIPAL(
            kcontext, cache, byref(princ)
        )
        if krb5_error_code != 0:
            _LOGGER.debug(
                'krb5_cc_get_principal failed, rc = %d', krb5_error_code
            )
            return None

        cleanups.append(lambda: _KRB5_FREE_PRINCIPAL(kcontext, princ))

        # char *name;
        # retval = krb5_unparse_name(kcontext, princ, &name);
        name = c_char_p()
        krb5_error_code = _KRB5_UNPARSE_NAME(
            kcontext, princ, byref(name)
        )
        if krb5_error_code != 0:
            _LOGGER.debug(
                'krb5_cc_get_principal failed, rc = %d', krb5_error_code
            )
            return None

        cleanups.append(lambda: _KRB5_FREE_UNPARSED_NAME(kcontext, name))
        return name.value.decode()

    finally:
        for cleanup in reversed(cleanups):
            cleanup()


def get_host_realm(hostname):
    """Return list of kerberos realms given hostname.

    If Kerberos libraries cannot be loaded, return None.
    """
    if not _check_funcs():
        _LOGGER.debug(
            'krb5_ functions are not loaded: gssapi_krb5_%s', _GSSAPI
        )
        return None

    cleanups = []
    try:
        # krb5_error_code retval = 0;
        # krb5_context kcontext;
        #
        # retval = krb5_init_context(&kcontext);
        kcontext = c_void_p()
        krb5_error_code = _KRB5_INIT_CONTEXT(byref(kcontext))
        if krb5_error_code != 0:
            _LOGGER.debug('krb5_init_context failed, rc = %d', krb5_error_code)
            return None

        cleanups.append(lambda: _KRB5_FREE_CONTEXT(kcontext))
        # char **realm_list = NULL;
        # retval = krb5_get_host_realm(kcontext, hostname, &realm_list);
        realm_list = _CHAR_PP()
        krb5_error_code = _KRB5_GET_HOST_REALM(
            kcontext,
            hostname.encode('utf-8'),
            byref(realm_list)
        )

        if krb5_error_code != 0:
            _LOGGER.debug(
                'krb5_get_host_realm failed, rc = %d', krb5_error_code
            )
            return None

        cleanups.append(lambda: _KRB5_FREE_HOST_REALM(kcontext, realm_list))
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
        for cleanup in reversed(cleanups):
            cleanup()


__all__ = [
    'get_host_realm',
]
