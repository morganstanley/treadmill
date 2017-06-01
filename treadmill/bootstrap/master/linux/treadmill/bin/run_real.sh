#!/bin/sh

# This script is not in chroot yet, so need to resolve local directory.

CHROOT={{ chroot }}
ECHO={{ echo }}
GREP={{ grep }}
LS={{ ls }}
MKDIR={{ mkdir }}
MOUNT={{ mount }}
RM={{ rm }}

<<<<<<< HEAD:local/linux/master/treadmill/bin/run_real.sh
# Look at ALL directories
=======
unset KRB5CCNAME
unset KRB5_KTNAME

# Look at ALL directories, e.g. .mslinks
>>>>>>> ms:lib/python/treadmill/bootstrap/master/linux/treadmill/bin/run_real.sh
for DIR in $(ls -a /); do
    # Ignore . and .. directories
    if [[ "${DIR}" != "." && "${DIR}" != ".." && -d /${DIR} ]]; then
        $MKDIR -p {{ dir }}/${DIR}
        $MOUNT -n --rbind /${DIR} {{ dir }}/${DIR}
    fi
done

<<<<<<< HEAD:local/linux/master/treadmill/bin/run_real.sh
=======
# Do a one time generation of the host ticket before starting services. There
# will be a service in charge or keeping tickets refreshed (not the chroot).
{{ dir }}/treadmill/bin/host_tickets.sh -o {{ dir }}/treadmill/spool/krb5cc_host

>>>>>>> ms:lib/python/treadmill/bootstrap/master/linux/treadmill/bin/run_real.sh
cd {{ dir }}

# Starting svscan
export PATH={{ s6 }}/bin:$PATH
exec $CHROOT {{ dir }}                       \
    {{ s6 }}/bin/s6-envdir /treadmill/env    \
    {{ s6 }}/bin/s6-svscan /treadmill/init
