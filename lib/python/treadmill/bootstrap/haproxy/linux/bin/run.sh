#!/bin/sh

DIR={{ dir  }}
ECHO={{ echo }}
LS={{ ls }}
RM={{ rm }}
IONICE={{ ionice }}
CHOWN={{ chown }}
S6={{ s6 }}
PID1={{ pid1 }}
TREADMILL={{ treadmill }}
TREADMILL_ID={{ treadmillid }}

for SVC in $($LS {{ dir }}/init); do
    if [ ! -d $TREADMILL/local/linux/haproxy/init/$SVC ]; then
        $RM -rf $DIR/init/$SVC
    else
        $ECHO $SVC configuration is up to date.
    fi
done

$CHOWN -R $TREADMILL_ID $DIR

export PATH=$S6/bin:$PATH

# Starting svscan
exec $IONICE -c2 -n0 $S6/bin/s6-envdir $DIR/env                       \
    $TREADMILL/bin/treadmill sproc --cell -                           \
        exec --                                                       \
        $PID1 -p                                                      \
        $S6/bin/s6-setuidgid $TREADMILL_ID                            \
        $S6/bin/s6-svscan $DIR/init
