#!/bin/sh

# Exit if any command fails
set -e

CHROOT={{ chroot }}
ECHO={{ echo }}
GREP={{ grep }}
LS={{ ls }}
MKDIR={{ mkdir }}
MOUNT={{ mount }}
RM={{ rm }}
S6_SVSCANCTL={{ s6 }}/bin/s6-svscanctl

export PATH="{{s6}}/bin:${PATH}"
# XXX(boysson): This is used in reset_services.sh. should be defined there
export TREADMILL_S6="{{ s6 }}"

$ECHO "#####################################################################"
$ECHO "Starting."
$ECHO "#####################################################################"

# Recalculate cgroup limits.
$ECHO "#####################################################################"
$ECHO "Re-apply Treadmill cgroup settings."
{{ treadmill }}/bin/treadmill sproc cginit                             \
    --cpu {{ treadmill_cpu}}                                           \
    --mem {{ treadmill_mem }}                                          \
    --mem-core {{ treadmill_core_mem }}

# remove extra services
$ECHO "#####################################################################"
$ECHO "Remove legacy services."
for SVC in `$LS {{ dir }}/init`; do
    if [ ! -d {{ treadmill }}/local/linux/node/init/$SVC ]; then
        $RM -vrf {{ dir }}/init/${SVC}
    else
        $ECHO ${SVC} configuration is up to date.
    fi
done

# Run fixups, if any
$ECHO "#####################################################################"
$ECHO "Apply fixups (pre)."
{{ dir }}/bin/fixups-pre.sh

# Reevaluate init directory.
$ECHO "#####################################################################"
$ECHO "Start/stop new/old servives."
$S6_SVSCANCTL -an {{ dir }}/init

# Upgrade remaining services.
$ECHO "#####################################################################"
$ECHO "Upgrade remaining services."
{{ treadmill }}/sbin/reset_services.sh \
    {{ dir }}/init {{ treadmill }}/etc/reset/node_services

# Run fixups, if any
$ECHO "#####################################################################"
$ECHO "Apply fixups (post)."
{{ dir }}/bin/fixups-post.sh

$ECHO "#####################################################################"
$ECHO "Done."
$ECHO "#####################################################################"

exit 0

