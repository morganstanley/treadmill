#!/bin/sh
#
# Reboot local node.

SLEEP={{ sleep }}
ECHO={{ echo }}
REBOOT={{ reboot }}

$ECHO $REBOOT -noexception -nooptout -noschedule -nouptime
$REBOOT -noexception -nooptout -noschedule -nouptime

$ECHO Reboot failed.

while true; do $SLEEP 10000; done
