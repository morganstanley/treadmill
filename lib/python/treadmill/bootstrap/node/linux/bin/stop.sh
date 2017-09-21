#!/bin/sh

exec > {{ dir }}/stop.log
exec 2>&1

ECHO={{ echo }}

unset KRB5CCNAME
unset KRB5_KTNAME

export PATH={{ s6 }}/bin:${PATH}

${ECHO} Done.
