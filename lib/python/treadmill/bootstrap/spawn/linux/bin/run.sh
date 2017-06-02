#!/bin/sh

DIR={{ dir }}
ECHO={{ echo }}
LS={{ ls }}
RM={{ rm }}
IONICE={{ ionice }}
CHOWN={{ chown }}
S6={{ s6 }}
PID1={{ pid1 }}
TREADMILL={{ treadmill }}
TREADMILL_ID={{ treadmillid }}
TREADMILL_SPAWN={{ treadmill_spawn }}

# Make sure ulimits are extremely large
ulimit -n 131072
ulimit -u 65536

$ECHO "set open files to $(ulimit -Sn)"
$ECHO "set max user processes to $(ulimit -Su)"

$CHOWN -R $TREADMILL_ID $DIR

export PATH=$S6/bin:$TREADMILL_SPAWN:${PATH}

for SVC in $($LS {{ dir }}/init); do
    $GREP {{ dir }}/init/$SVC/\$ {{ dir }}/.install > /dev/null
    if [ $? != 0 ]; then
        $ECHO Removing extra service: $SVC
        $RM -vrf {{ dir }}/init/$SVC
    fi
done

# Starting svscan
exec $IONICE -c2 -n0 $S6/bin/s6-envdir $DIR/env                       \
    $TREADMILL/bin/treadmill sproc --cell -                           \
        exec --                                                       \
        $PID1 -p                                                      \
        $S6/bin/s6-setuidgid $TREADMILL_ID                            \
        $S6/bin/s6-svscan $DIR/init
