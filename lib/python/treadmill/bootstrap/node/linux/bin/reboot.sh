#!/bin/sh
#
# Reboot local node.

SLEEP="{{ _alias.sleep }}"
ECHO="{{ _alias.echo }}"
REBOOT="{{ _alias.reboot }}"

set -e

while [ 1 ];
do
    ${REBOOT} && break
    ${ECHO} "Reboot failed, retrying in 60s ..."
    ${SLEEP} 60
done

exec ${SLEEP} inf
