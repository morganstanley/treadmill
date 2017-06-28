#!/bin/sh

exec > {{ dir }}/stop.log
exec 2>&1

S6={{ s6 }}
ECHO={{ echo }}

unset KRB5CCNAME
unset KRB5_KTNAME

export PATH={{ s6 }}/bin:${PATH}

{{ s6_svc }} -wd {{ dir }}/init/cleanup
{{ s6_svscanctl }} -t {{ dir }}/init

${ECHO} Done.
