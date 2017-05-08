#!/bin/sh

exec > {{ dir }}/stop.log
exec 2>&1

S6={{ s6 }}

unset KRB5CCNAME
unset KRB5_KTNAME

export PATH=$S6:${PATH}

$S6/bin/s6-svc -wd {{ dir }}/init/cleanup
$S6/bin/s6-svscanctl -t {{ dir }}/init

$ECHO Done.
