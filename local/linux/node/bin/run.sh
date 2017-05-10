#!/bin/sh

CHROOT={{ chroot }}
ECHO={{ echo }}
GREP={{ grep }}
LS={{ ls }}
MKDIR={{ mkdir }}
MOUNT={{ mount }}
RM={{ rm }}
IONICE={{ ionice }}


# Setup /a so that NFS works inside the containers
#{{ treadmill }}/sbin/configure_mounts.sh

export PATH={{ s6 }}/bin:${PATH}

$RM -f {{ dir }}/init/server_init/zkid.pickle

# Enable ip forwarding.
$ECHO Enabling /proc/sys/net/ipv4/ip_forward
$ECHO 1 > /proc/sys/net/ipv4/ip_forward

# Starting svscan
exec $IONICE -c2 -n0 \
    {{ s6 }}/bin/s6-envdir {{ dir }}/env                                    \
    {{ treadmill_bin }} sproc                                               \
        --cell - cgroup                                                     \
        cleanup --delete --apps --core                                      \
        mount                                                               \
        init --cpu {{ treadmill_cpu}}                                       \
             --mem {{ treadmill_mem }}                                      \
             --mem-core {{ treadmill_core_mem }}                            \
             --cpu-cores {{ treadmill_cpu_cores }}                          \
        migrate -t system                                                   \
        exec --into cpu:/treadmill/core                                     \
             --into memory:/treadmill/core                                  \
             --into cpuset:/treadmill --                                    \
        {{ pid1 }} -m -p                                                    \
        {{ s6 }}/bin/s6-svscan {{ dir }}/init
