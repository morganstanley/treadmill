#!/bin/sh

CHROOT={{ chroot }}
ECHO={{ echo }}
GREP={{ grep }}
LS={{ ls }}
MKDIR={{ mkdir }}
MOUNT={{ mount }}
RM={{ rm }}
IONICE={{ ionice }}


for SVC in `$LS {{ dir }}/init`; do
    if [ ! -d {{ treadmill }}/local/linux/node/init/$SVC ]; then
        $RM -rf {{ dir }}/init/$SVC
    else
        $ECHO $SVC configuration is up to date.
    fi
done

unset KRB5CCNAME
unset KRB5_KTNAME

# Setup /a so that NFS works inside the containers
{{ treadmill }}/sbin/configure_mounts.sh

# Do a one time generation of the host ticket before starting services. There
# will be a service in charge or keeping tickets refreshed.
{{ treadmill }}/sbin/host_tickets.sh -o {{ dir }}/spool/krb5cc_host

export PATH={{ s6 }}/bin:${PATH}

$RM -f {{ dir }}/init/server_init/zkid.pickle

# Enable ip forwarding.
$ECHO Enabling /proc/sys/net/ipv4/ip_forward
$ECHO 1 > /proc/sys/net/ipv4/ip_forward

# Starting svscan
exec $IONICE -c2 -n0 {{ s6 }}/bin/s6-envdir {{ dir }}/env                  \
    {{ treadmill }}/bin/treadmill sproc --cell - cgroup                    \
        cleanup --delete --apps --core                                     \
        mount                                                              \
        init --cpu {{ treadmill_cpu}}                                      \
             --mem {{ treadmill_mem }}                                     \
             --mem-core {{ treadmill_core_mem }}                           \
        migrate -t system                                                  \
        exec --into cpu:/treadmill/core                                    \
             --into memory:/treadmill/core --                              \
        {{ pid1 }} -m -p                                                   \
        {{ s6 }}/bin/s6-svscan {{ dir }}/init
