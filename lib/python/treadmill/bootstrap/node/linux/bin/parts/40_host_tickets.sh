#!/bin/sh

# Creates host tickets from host keytab and store it in the configured ticket
# location.
#

KINIT="{{ _alias.kinit }}"
KLIST="{{ _alias.klist }}"

function refresh_host_ticket() {
    export KRB5CCNAME="FILE:{{ treadmill_host_ticket }}"

    ${KINIT} -k -l 2d

    # Display tickets cache and host keytabs for debugging purposes.
    ${KLIST} -5
    ${KLIST} -k
}

refresh_host_ticket
