#!/bin/sh

<<<<<<< HEAD:local/linux/node/bin/run.sh
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
=======
CHROOT={{ _alias.chroot }}
ECHO={{ _alias.echo }}
GREP={{ _alias.grep }}
LS={{ _alias.ls }}
MKDIR={{ _alias.mkdir }}
MOUNT={{ _alias.mount }}
RM={{ _alias.rm }}
IONICE={{ _alias.ionice }}

unset KRB5CCNAME
unset KRB5_KTNAME

if [ -f {{ dir }}/bin/configure_mounts.sh ]; then
    {{ dir }}/bin/configure_mounts.sh
fi

# Do a one time generation of the host ticket before starting services. There
# will be a service in charge or keeping tickets refreshed.
if [ -f {{ dir }}/bin/host_tickets.sh ]; then
    {{ dir }}/bin/host_tickets.sh -o {{ dir }}/spool/krb5cc_host
fi
>>>>>>> ms:lib/python/treadmill/bootstrap/node/linux/bin/run.sh

export PATH={{ s6 }}/bin:${PATH}

$RM -f {{ dir }}/init/server_init/zkid.pickle

# Enable ip forwarding.
$ECHO Enabling /proc/sys/net/ipv4/ip_forward
$ECHO 1 > /proc/sys/net/ipv4/ip_forward

# Starting svscan
<<<<<<< HEAD:local/linux/node/bin/run.sh
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
=======
exec $IONICE -c2 -n0 {{ s6 }}/bin/s6-envdir {{ dir }}/env                  \
    {{ treadmill }}/bin/treadmill sproc --cell - cgroup                    \
        cleanup --delete --apps --core                                     \
        mount                                                              \
        init --cpu {{ treadmill_cpu}}                                      \
             --mem {{ treadmill_mem }}                                     \
             --mem-core {{ treadmill_core_mem }}                           \
             --cpu-cores {{ treadmill_cpu_cores }}                         \
        migrate -t system                                                  \
        exec --into cpu:/treadmill/core                                    \
             --into memory:/treadmill/core                                 \
             --into cpuset:/treadmill --                                   \
        {{ _alias.pid1 }} -m -p                                            \
>>>>>>> ms:lib/python/treadmill/bootstrap/node/linux/bin/run.sh
        {{ s6 }}/bin/s6-svscan {{ dir }}/init
