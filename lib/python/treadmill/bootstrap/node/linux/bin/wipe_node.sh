#!/bin/sh

ECHO="{{ _alias.echo}}"
LOSETUP="{{ _alias.losetup }}"
PVREMOVE="{{ _alias.pvremove }}"
RM="{{ _alias.rm }}"
VGCHANGE="{{ _alias.vgchange }}"
VGREMOVE="{{ _alias.vgremove }}"

set -x

${VGCHANGE} -v --autobackup n --activate n "treadmill"
${VGREMOVE} -v --force "treadmill"

for LOOP in $(${ECHO} /dev/loop*)
do
    ${PVREMOVE} -v --force ${LOOP}
    ${LOSETUP} -vd ${LOOP}
done

cd / && ${RM} -vrf "{{ dir }}"
