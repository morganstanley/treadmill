#!/bin/sh

ECHO="{{ _alias.echo }}"
GREP="{{ _alias.grep }}"
IONICE="{{ _alias.ionice }}"
RM="{{ _alias.rm }}"
PID1="{{ _alias.pid1 }}"
ENVDIR="{{ _alias.s6_envdir }}"
TMBIN="{{ treadmill }}/bin/treadmill34"

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
# Enable ip forwarding.
${ECHO} -e "\nEnabling /proc/sys/net/ipv4/ip_forward"
${ECHO} 1 > /proc/sys/net/ipv4/ip_forward

###############################################################################
${ECHO} -e "\nCleaning up local install."

for SVCDIR in init init1; do
    for SVC in "{{ dir }}/${SVCDIR}"/*/; do
        ${GREP} "${SVC}\$" "{{ dir }}/.install" >/dev/null
        if [ $? != 0 ]; then
            ${ECHO} Removing extra service: ${SVC}.
            ${RM} -vrf "${SVC}"
        else
            ${RM} -vf "${SVC}/data/exits"/*
        fi
    done
done

for PART in "{{ dir }}/bin/parts"/*; do
    ${GREP} "${PART}\$" "{{ dir }}/.install" >/dev/null
    if [ $? != 0 ]; then
        ${ECHO} Removing extra part script: ${PART}.
        ${RM} -vf "${PART}"
    fi
done

# Cleanup zkids (FIXME: figure out why we still need this)
${RM} -vf "{{ dir }}/init*/*/zkid.pickle"

# Cleanup the watchdog directory.
${RM} -vf "{{ dir }}/watchdogs"/*

# Cleanup the running directory.
${RM} -vf "{{ dir }}/running"/*

# Cleanup the cleanup directory.
${RM} -vf "{{ dir }}/cleanup"/*

# Cleanup the cleaning directory.
${RM} -vf "{{ dir }}/cleaning"/*

# Cleanup the tombstone directories.
for TOMBSTONEDIR in "{{ dir }}/tombstones"/*/; do
    ${RM} -vf "${TOMBSTONEDIR}"/*
done

###############################################################################
${ECHO} -e "\nRunning setup scripts."
run_parts "{{ dir }}/bin/parts"

###############################################################################
# TODO: Move all of Treadmill's benchmarking into boot.
{% if benchmark %}
    ${ECHO} Start benchmark
    {{ dir }}/bin/benchmark.sh
{% endif %}

###############################################################################
# Start treadmill

# Set our IO priority to "Best Effort" / maximum priority.
# Enter a private mount and pid namespaces.
# Re-read our environment variables in case parts added some.
# Execute into Treadmill boot.
exec \
    ${IONICE} -c2 -n0 \
    ${PID1} -m -p --propagation slave \
    ${ENVDIR} "{{ dir }}/env" \
    ${TMBIN} \
        sproc boot
