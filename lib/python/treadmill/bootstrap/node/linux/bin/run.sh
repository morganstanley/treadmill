#!/bin/sh

CHROOT={{ _alias.chroot }}
ECHO={{ _alias.echo }}
GREP={{ _alias.grep }}
IONICE={{ _alias.ionice }}
LS={{ _alias.ls }}
MKDIR={{ _alias.mkdir }}
MOUNT={{ _alias.mount }}
RM={{ _alias.rm }}
TOUCH={{ _alias.touch }}

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

export PATH={{ _alias.s6 }}/bin:${PATH}

$RM -f {{ dir }}/init/server_init/zkid.pickle

# Enable ip forwarding.
$ECHO Enabling /proc/sys/net/ipv4/ip_forward
$ECHO 1 > /proc/sys/net/ipv4/ip_forward

for SVCDIR in init init1; do
    for SVC in $($LS {{ dir }}/$SVCDIR); do
        $GREP {{ dir }}/$SVCDIR/$SVC/\$ {{ dir }}/.install > /dev/null
        if [ $? != 0 ]; then
            $ECHO Removing extra service: $SVC
            $RM -vrf {{ dir }}/$SVCDIR/$SVC
        fi
    done
    $RM -vf {{ dir }}/$SVCDIR/*/data/exits/*
done

# Cleanup the watchdog directory.
$RM -vf {{ dir }}/watchdogs/*

# Cleanup the running directory.
$RM -vf {{ dir }}/running/*

# Cleanup the cleanup directory but add cleanup file first.
for INSTANCE in {{ dir }}/cleanup/*; do
    if [[ -d $INSTANCE ]]; then
        $TOUCH $INSTANCE/data/cleanup
    fi
done
$RM -vf {{ dir }}/cleanup/*

# Cleanup the cleaning directory.
$RM -vf {{ dir }}/cleaning/*

{% if benchmark %}
    $ECHO Start benchmark
    {{ dir }}/bin/benchmark.sh
{% endif %}

# Create cgroup layout.
# TODO: cginit missing --cpu-cores argument.
{{ treadmill_bin }} sproc cginit                               \
    --cpu {{ treadmill_cpu }}                                              \
    --mem {{ treadmill_mem }}                                              \
    --mem-core {{ treadmill_core_mem }}


# Starting svscan
exec $IONICE -c2 -n0 {{ _alias.s6_envdir }} {{ dir }}/env                  \
    {{ treadmill_bin }} sproc --cell - cgroup                    \
        cleanup --delete --apps --core                                     \
        mount                                                              \
        init --cpu {{ treadmill_cpu }}                                     \
             --mem {{ treadmill_mem }}                                     \
             --mem-core {{ treadmill_core_mem }}                           \
             --cpu-cores {{ treadmill_cpu_cores }}                         \
        migrate -t system                                                  \
        exec --into cpu:/treadmill/core                                    \
             --into memory:/treadmill/core                                 \
             --into cpuset:/treadmill --                                   \
        {{ _alias.pid1 }} -m -p                                            \
        {{ _alias.s6_svscan }}  -s {{ dir }}/init
