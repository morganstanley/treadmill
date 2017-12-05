#!/bin/sh

# Treadmill fixups (post)
#
# Collection of quick fixes that should be applied during node live upgrades
# *after* the new services have been installed/started.

# Each fixup here should have a comment and a associated JIRA.

# Fix stale ephemeral port rules left behind by TREADMILL-456
#
# Remove all rules that don't have a matching app in apps/
CHROOT={{ _alias.chroot }}
ECHO={{ _alias.echo }}
GREP={{ _alias.grep }}
LS={{ _alias.ls }}
MKDIR={{ _alias.mkdir }}
MOUNT={{ _alias.mount }}
RM={{ _alias.rm }}
FIND={{ _alias.find }}

echo "- Fixing up stale DNAT forwarding rules"
for RULE in $(${LS} -1 "{{ dir }}/rules/"dnat:* 2>/dev/null)
do
    APP=$(echo ${RULE} | cut -d ':' -f 2)
    if [ ! -d "{{ dir }}/apps/${APP}/" ]
    then
        ${RM} -f "${RULE}"
    fi
done

echo "- Finishing pre 2.0.121 localdisk service upgrade"
for R in $(${FIND} "{{ dir }}/localdisk_svc/" -maxdepth 1 -type l 2>/dev/null)
do
    ${RM} -f ${R}
done

echo "- Finishing pre 2.0.121 cgroup service upgrade"
for R in $(${FIND} "{{ dir }}/cgroup_svc/" -maxdepth 1 -type l 2>/dev/null)
do
    ${RM} -f ${R}
done

echo "- Finishing pre 2.0.121 network service upgrade"
for R in $(${FIND} "{{ dir }}/network_svc/" -maxdepth 1 -type l 2>/dev/null)
do
    ${RM} -f ${R}
done

exit 0
