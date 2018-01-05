#!/bin/sh

exec > {{ dir }}/stop.log
exec 2>&1

ECHO={{ _alias.echo }}
S6={{ s6 }}

export PATH=$S6/bin:$PATH

$ECHO "Terminating svscan in {{ dir }}/init"

{{ _alias.s6_svscanctl }} -q {{ dir }}/init
