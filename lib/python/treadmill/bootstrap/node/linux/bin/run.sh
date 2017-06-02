#!/bin/sh

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

export PATH={{ s6 }}/bin:${PATH}

$RM -f {{ dir }}/init/server_init/zkid.pickle

# Enable ip forwarding.
$ECHO Enabling /proc/sys/net/ipv4/ip_forward
$ECHO 1 > /proc/sys/net/ipv4/ip_forward

for SVC in $($LS {{ dir }}/init); do
    $GREP {{ dir }}/init/$SVC/\$ {{ dir }}/.install > /dev/null
    if [ $? != 0 ]; then
        $ECHO Removing extra service: $SVC
        $RM -vrf {{ dir }}/init/$SVC
    fi
done

$RM -vrf {{ dir }}/init/*/data/exits/*

# Starting svscan
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
        {{ s6 }}/bin/s6-svscan {{ dir }}/init
