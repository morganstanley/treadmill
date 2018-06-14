#!/bin/sh

ECHO={{ _alias.echo }}

unset KRB5CCNAME
unset KRB5_KTNAME

###############################################################################
function run_parts {
    set -e

    for SCRIPT in $(LC_ALL=C; echo "$1/*" | sort); do
        [ -d ${SCRIPT} ] && continue
        [ ! -x ${SCRIPT} ] && continue
        SCRIPTNAME="${SCRIPT##*/[0-9][0-9]_}"
        SCRIPTNAME="${SCRIPTNAME%%.sh}"

        ${ECHO} -e "\nStarting '${SCRIPTNAME}':"
        ${SCRIPT}
        ${ECHO} "Finished '${SCRIPTNAME}'"
    done
}

run_parts $1
