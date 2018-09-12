"""Wrapper for kerberos module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys

# on windows the name of the kerberos module is different
# so sys.modules needs to be updated to be able to 'import kerberos'
if os.name == 'nt':
    import winkerberos  	# pylint: disable=import-error
    sys.modules['kerberos'] = winkerberos

import kerberos             # pylint: disable=import-error


GSSError = kerberos.GSSError 	# pylint: disable=C0103
GSS_C_MUTUAL_FLAG = kerberos.GSS_C_MUTUAL_FLAG
GSS_C_SEQUENCE_FLAG = kerberos.GSS_C_SEQUENCE_FLAG
GSS_C_INTEG_FLAG = kerberos.GSS_C_INTEG_FLAG
GSS_C_CONF_FLAG = kerberos.GSS_C_CONF_FLAG
AUTH_GSS_COMPLETE = kerberos.AUTH_GSS_COMPLETE

# pylint: disable=invalid-name
authGSSClientInit = kerberos.authGSSClientInit
authGSSClientStep = kerberos.authGSSClientStep
authGSSClientResponse = kerberos.authGSSClientResponse
authGSSClientUnwrap = kerberos.authGSSClientUnwrap
authGSSClientResponse = kerberos.authGSSClientResponse
authGSSClientWrap = kerberos.authGSSClientWrap
