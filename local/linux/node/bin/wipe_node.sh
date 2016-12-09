#!/bin/sh

LOSETUP={{ losetup }}
VGCHANGE={{ vgchange }}
VGREMOVE={{ vgremove }}
PVREMOVE={{ pvremove }}
RM={{ rm }}
LS={{ ls }}

${VGCHANGE} -v --autobackup n --activate n "treadmill"
${VGREMOVE} -v --force "treadmill"

for LOOP in $(${LS} /dev/loop*)
do
    ${PVREMOVE} -v --force ${LOOP}
    ${LOSETUP} -vd ${LOOP}
done

cd /tmp && ${RM} -vrf {{ dir }}
