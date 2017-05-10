#!/bin/sh

# This script is not in chroot yet, so need to resolve local directory.

CHROOT={{ chroot }}
ECHO={{ echo }}
GREP={{ grep }}
LS={{ ls }}
MKDIR={{ mkdir }}
MOUNT={{ mount }}
RM={{ rm }}

# Look at ALL directories
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
