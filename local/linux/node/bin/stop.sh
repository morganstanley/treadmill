#!/bin/sh

exec > {{ dir }}/stop.log
exec 2>&1

ECHO={{ echo }}
DATE={{ date }}
LS={{ ls }}
RM={{ rm }}
SLEEP={{ sleep }}
S6={{ s6 }}


unset KRB5CCNAME
unset KRB5_KTNAME

export PATH=$S6:${PATH}

# Mark server as down.
$S6/bin/s6-svc -d {{ dir }}/init/server_init
$S6/bin/s6-svc -d {{ dir }}/init/eventd
$S6/bin/s6-svc -d {{ dir }}/init/appcfgmgr

RUNNING_COUNT=$($LS {{ dir }}/running | wc -l)
if [[ $RUNNING_COUNT -gt 3 ]]; then RUNNING_COUNT=3; fi

$RM {{ dir }}/running/*

function wait_until_empty {
    DIR=$1
    $ECHO Wait for $DIR to become empty.

    for i in {1..3}; do
        COUNT=$($LS $DIR | wc -l)
        $ECHO $($DATE) - $COUNT items left.
        $LS -l $DIR
        if [ $COUNT == 0 ]; then break; fi
        $SLEEP $COUNT
    done
}

$SLEEP 2
$SLEEP $RUNNING_COUNT

wait_until_empty {{ dir }}/cleanup

$ECHO Done.
