"""Replaces the use of python-gssapi with kerberos in ldap3.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import base64
import socket

from ldap3.core.exceptions import LDAPCommunicationError
from ldap3.protocol.sasl.sasl import send_sasl_negotiation
from ldap3.protocol.sasl.sasl import abort_sasl_negotiation

from treadmill import kerberoswrapper as kerberos

NO_SECURITY_LAYER = 1
INTEGRITY_PROTECTION = 2
CONFIDENTIALITY_PROTECTION = 4


def sasl_gssapi(connection, controls):
    """
    Performs a bind using the Kerberos v5 ("GSSAPI") SASL mechanism
    from RFC 4752. Does not support any security layers, only authentication!

    sasl_credentials can be empty or a tuple with one or two elements.
    The first element determines which service principal to request a ticket
    for and can be one of the following:

    - None or False, to use the hostname from the Server object
    - True to perform a reverse DNS lookup to retrieve the canonical hostname
      for the hosts IP address
    - A string containing the hostname

    The optional second element is what authorization ID to request.

    - If omitted or None, the authentication ID is used as the authorization ID
    - If a string, the authorization ID to use. Should start with "dn:" or
      "user:".
    """
    # pylint: disable=too-many-branches
    target_name = None
    authz_id = b''
    if connection.sasl_credentials:
        if (len(connection.sasl_credentials) >= 1 and
                connection.sasl_credentials[0]):
            if connection.sasl_credentials[0] is True:
                hostname = \
                    socket.gethostbyaddr(connection.socket.getpeername()[0])[0]
                target_name = 'ldap@' + hostname

            else:
                target_name = 'ldap@' + connection.sasl_credentials[0]
        if (len(connection.sasl_credentials) >= 2 and
                connection.sasl_credentials[1]):
            authz_id = connection.sasl_credentials[1].encode("utf-8")
    if target_name is None:
        target_name = 'ldap@' + connection.server.host

    gssflags = (
        kerberos.GSS_C_MUTUAL_FLAG |
        kerberos.GSS_C_SEQUENCE_FLAG |
        kerberos.GSS_C_INTEG_FLAG |
        kerberos.GSS_C_CONF_FLAG
    )

    _, ctx = kerberos.authGSSClientInit(target_name, gssflags=gssflags)

    in_token = b''
    try:
        while True:
            status = kerberos.authGSSClientStep(
                ctx,
                base64.b64encode(in_token).decode('ascii')
            )
            out_token = kerberos.authGSSClientResponse(ctx) or ''
            result = send_sasl_negotiation(
                connection,
                controls,
                base64.b64decode(out_token)
            )
            in_token = result['saslCreds'] or b''
            if status == kerberos.AUTH_GSS_COMPLETE:
                break

        kerberos.authGSSClientUnwrap(
            ctx,
            base64.b64encode(in_token).decode('ascii')
        )
        unwrapped_token = base64.b64decode(
            kerberos.authGSSClientResponse(ctx) or ''
        )

        if len(unwrapped_token) != 4:
            raise LDAPCommunicationError('Incorrect response from server')

        server_security_layers = unwrapped_token[0]
        if not isinstance(server_security_layers, int):
            server_security_layers = ord(server_security_layers)
        if server_security_layers in (0, NO_SECURITY_LAYER):
            if unwrapped_token.message[1:] != '\x00\x00\x00':
                raise LDAPCommunicationError(
                    'Server max buffer size must be 0 if no security layer'
                )
        if not server_security_layers & NO_SECURITY_LAYER:
            raise LDAPCommunicationError(
                'Server requires a security layer, but this is not implemented'
            )

        client_security_layers = bytearray([NO_SECURITY_LAYER, 0, 0, 0])
        kerberos.authGSSClientWrap(
            ctx,
            base64.b64encode(
                bytes(client_security_layers) + authz_id
            ).decode('ascii')
        )
        out_token = kerberos.authGSSClientResponse(ctx) or ''

        return send_sasl_negotiation(
            connection,
            controls,
            base64.b64decode(out_token)
        )
    except (kerberos.GSSError, LDAPCommunicationError):
        abort_sasl_negotiation(connection, controls)
        raise
