#!/bin/sh

# This script is not in chroot yet, so need to resolve local directory.

CHROOT={{ chroot }}
ECHO={{ echo }}
GREP={{ grep }}
LS={{ ls }}
MKDIR={{ mkdir }}
MOUNT={{ mount }}
RM={{ rm }}

unset KRB5CCNAME
unset KRB5_KTNAME

for SVC in $($LS {{ dir }}/treadmill/init); do
    $GREP {{ dir }}/treadmill/init/$SVC/\$ {{ dir }}/.install > /dev/null
    if [ $? != 0 ]; then
        $ECHO Removing extra service: $SVC
        $RM -vrf {{ dir }}/treadmill/init/$SVC
    fi
done

# Look at ALL directories, e.g. .mslinks
for DIR in $(ls -a /); do
    # Ignore . and .. directories
    if [[ "${DIR}" != "." && "${DIR}" != ".." && -d /${DIR} ]]; then
        $MKDIR -p {{ dir }}/${DIR}
        $MOUNT -n --rbind /${DIR} {{ dir }}/${DIR}
    fi
done

cd {{ dir }}

# Starting svscan
export PATH={{ s6 }}/bin:$PATH
exec $CHROOT {{ dir }}                       \
    {{ s6 }}/bin/s6-envdir /treadmill/env    \
    {{ s6 }}/bin/s6-svscan /treadmill/init
