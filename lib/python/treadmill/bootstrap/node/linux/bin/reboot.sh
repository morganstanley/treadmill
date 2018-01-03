#!/bin/sh
#
# Reboot local node.

SLEEP={{ _alias.sleep }}
ECHO={{ _alias.echo }}
REBOOT={{ _alias.reboot }}

$ECHO $REBOOT -noexception -nooptout -noschedule -nouptime
$REBOOT -noexception -nooptout -noschedule -nouptime

$ECHO Reboot failed.

while true; do $SLEEP 10000; done
