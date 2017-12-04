#!/bin/sh

exec > {{ dir }}/stop.log
exec 2>&1

ECHO={{ _alias.echo }}

unset KRB5CCNAME
unset KRB5_KTNAME

export PATH={{ _alias.s6 }}/bin:${PATH}

${ECHO} Done.
