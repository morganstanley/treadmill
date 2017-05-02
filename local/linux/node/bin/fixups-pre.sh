#!/bin/sh

# Treadmill fixups (pre)
#
# Collection of quick fixes that should be applied during node live upgrades.
# *before* the new services have been installed/started.
#

# Each fixup here should have a comment and a associated JIRA.
CHROOT={{ chroot }}
ECHO={{ echo }}
GREP={{ grep }}
LS={{ ls }}
MKDIR={{ mkdir }}
MOUNT={{ mount }}
RM={{ rm }}
FIND={{ find }}


echo "- Preparing for pre 2.0.121 localdisk service upgrade"
${MKDIR} -p "{{ dir }}/localdisk_svc/resources/"
for R in $(${FIND} "{{ dir }}/localdisk_svc/" -maxdepth 1 -type l 2>/dev/null)
do
    ${CP} -d ${R} "{{ dir }}/localdisk_svc/resources/"
done

echo "- Preparing for pre 2.0.121 cgroup service upgrade"
${MKDIR} -p "{{ dir }}/cgroup_svc/resources/"
for R in $(${FIND} "{{ dir }}/cgroup_svc/" -maxdepth 1 -type l 2>/dev/null)
do
    ${CP} -d ${R} "{{ dir }}/cgroup_svc/resources/"
done

echo "- Preparing for pre 2.0.121 network service upgrade"
${MKDIR} -p "{{ dir }}/network_svc/resources/"
for R in $(${FIND} "{{ dir }}/network_svc/" -maxdepth 1 -type l 2>/dev/null)
do
    ${CP} -d ${R} "{{ dir }}/network_svc/resources/"
done

exit 0
