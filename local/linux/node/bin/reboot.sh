#!/bin/sh
#
# Reboot local node.

SLEEP={{ sleep }}
ECHO={{ echo }}
REBOOT={{ reboot }}

$ECHO $REBOOT -noexception -nooptout -noschedule -nouptime -noexec
$REBOOT -noexception -nooptout -noschedule -nouptime -noexec

$ECHO Reboot failed.

while true; do $SLEEP 10000; done
