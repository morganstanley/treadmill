#!/bin/sh

# This script is not in chroot yet, so need to resolve local directory.

CHROOT={{ chroot }}
ECHO={{ echo }}
GREP={{ grep }}
LS={{ ls }}
MKDIR={{ mkdir }}
MOUNT={{ mount }}
RM={{ rm }}

for SVC in `$LS {{ dir }}/treadmill/init`; do
    if [ ! -d {{ treadmill }}/local/linux/master/treadmill/init/$SVC ]; then
        $RM -rf {{ dir  }}/treadmill/init/$SVC
    else
        $ECHO $SVC configuration is up to date.
    fi
done

unset KRB5CCNAME
unset KRB5_KTNAME

# Look at ALL directories, e.g. .mslinks
for DIR in $(ls -a /); do
    # Ignore . and .. directories
    if [[ "${DIR}" != "." && "${DIR}" != ".." && -d /${DIR} ]]; then
        $MKDIR -p {{ dir }}/${DIR}
        $MOUNT -n --rbind /${DIR} {{ dir }}/${DIR}
    fi
done

# Do a one time generation of the host ticket before starting services. There
# will be a service in charge or keeping tickets refreshed (not the chroot).
{{ treadmill }}/sbin/host_tickets.sh -o {{ dir }}/treadmill/spool/krb5_cchost

cd {{ dir }}

# Starting svscan
export PATH={{ s6 }}/bin:$PATH
exec $CHROOT {{ dir }}                       \
    {{ s6 }}/bin/s6-envdir /treadmill/env    \
    {{ s6 }}/bin/s6-svscan /treadmill/init
