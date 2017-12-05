#!/bin/sh

LOSETUP={{ _alias.losetup }}
VGCHANGE={{ _alias.vgchange }}
VGREMOVE={{ _alias.vgremove }}
PVREMOVE={{ _alias.pvremove }}
RM={{ _alias.rm }}
LS={{ _alias.ls }}

${VGCHANGE} -v --autobackup n --activate n "treadmill"
${VGREMOVE} -v --force "treadmill"

for LOOP in $(${LS} /dev/loop*)
do
    ${PVREMOVE} -v --force ${LOOP}
    ${LOSETUP} -vd ${LOOP}
done

cd /tmp && ${RM} -vrf {{ dir }}
