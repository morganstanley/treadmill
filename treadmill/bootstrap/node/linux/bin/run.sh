#!/bin/sh

CHROOT={{ chroot }}
ECHO={{ echo }}
GREP={{ grep }}
LS={{ ls }}
MKDIR={{ mkdir }}
MOUNT={{ mount }}
RM={{ rm }}
IONICE={{ ionice }}

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

# Create cgroup layout.
# TODO: cginit missing --cpu-cores argument.
{{ treadmill}}/bin/treadmill sproc cginit                                  \
    --cpu {{ treadmill_cpu }}                                              \
    --mem {{ treadmill_mem }}                                              \
    --mem-core {{ treadmill_core_mem }}


# Starting svscan
exec $IONICE -c2 -n0 {{ _alias.s6_envdir }} {{ dir }}/env                  \
    {{ treadmill }}/bin/treadmill sproc --cell - cgroup                    \
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
