#!/bin/sh

ECHO={{ _alias.echo }}
GREP={{ _alias.grep}}
IONICE={{ _alias.ionice }}
RM={{ _alias.rm }}
S6={{ _alias.s6 }}
S6_ENVDIR={{ _alias.s6_envdir }}
S6_SVSCAN={{ _alias.s6_svscan }}

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

###############################################################################
${ECHO} -e "\nCleaning up local install."

for SVC in "{{ dir }}/init"/*/; do
    ${GREP} "${SVC}\$" "{{ dir }}/.install" >/dev/null
    if [ $? != 0 ]; then
        ${ECHO} Removing extra service: ${SVC}.
        ${RM} -vrf "${SVC}"
    else
        ${RM} -vf "${SVC}/data/exits"/*
    fi
done

for PART in "{{ dir }}/bin/parts"/*; do
    ${GREP} "${PART}\$" "{{ dir }}/.install" >/dev/null
    if [ $? != 0 ]; then
        ${ECHO} Removing extra part script: ${PART}.
        ${RM} -vf "${PART}"
    fi
done

###############################################################################
${ECHO} -e "\nRunning setup scripts."
run_parts "{{ dir }}/bin/parts"

###############################################################################
# Starting svscan
exec \
    ${IONICE} -c2 -n0 \
        ${S6_ENVDIR} {{ dir }}/env \
            ${S6_SVSCAN} {{ dir }}/init
