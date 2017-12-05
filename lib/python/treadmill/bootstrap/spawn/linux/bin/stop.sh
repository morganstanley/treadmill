#!/bin/sh

exec 2>&1

DIR={{ dir }}
ECHO={{ echo }}
S6={{ s6 }}

export PATH=$S6/bin:${PATH}

$ECHO "Terminating svscan in {{ dir }}/init"

$S6/bin/s6-svscanctl -q $DIR/init
