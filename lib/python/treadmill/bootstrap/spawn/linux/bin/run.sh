#!/bin/sh

DIR={{ dir }}
ECHO={{ _alias.echo }}
GREP={{ _alias.grep }}
LN={{ _alias.ln }}
LS={{ _alias.ls }}
RM={{ _alias.rm }}
IONICE={{ _alias.ionice }}
CHOWN={{ _alias.chown }}
S6={{ _alias.s6 }}
PID1={{ _alias.pid1 }}
TREADMILL={{ treadmill }}
TREADMILL_ID={{ treadmillid }}
TREADMILL_SPAWN={{ _alias.treadmill_spawn }}
TREADMILL_SPAWN_PATH={{ _alias.treadmill_spawn_path }}

# Update symlink
$ECHO "Updating treadmill-spawn symlink to $TREADMILL_SPAWN"
$LN -sf $TREADMILL_SPAWN {{ dir }}/bin/treadmill-spawn

# Make sure ulimits are extremely large
ulimit -n 131072
ulimit -u 65536

$ECHO "set open files to $(ulimit -Sn)"
$ECHO "set max user processes to $(ulimit -Su)"

$CHOWN -R $TREADMILL_ID $DIR

export PATH=$S6/bin:$TREADMILL_SPAWN_PATH:${PATH}

for SVC in $($LS {{ dir }}/init); do
    $GREP {{ dir }}/init/$SVC/\$ {{ dir }}/.install > /dev/null
    if [ $? != 0 ]; then
        $ECHO Removing extra service: $SVC
        $RM -vrf {{ dir }}/init/$SVC
    fi
done

# Starting svscan
exec $IONICE -c2 -n0 $S6/bin/s6-envdir $DIR/env                       \
    {{ treadmill }}/bin/treadmill sproc --cell -                          \
        exec --                                                       \
        $PID1 -p                                                      \
        $S6/bin/s6-setuidgid $TREADMILL_ID                            \
        $S6/bin/s6-svscan $DIR/init
