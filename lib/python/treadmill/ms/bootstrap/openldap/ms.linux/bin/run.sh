#!/bin/sh

CHOWN={{ _alias.chown }}
ECHO={{ _alias.echo }}
IONICE={{ _alias.ionice }}
LS={{ _alias.ls }}
PID1={{ _alias.pid1 }}
RM={{ _alias.rm }}
S6={{ _alias.s6 }}
S6_ENVDIR={{ _alias.s6_envdir }}
S6_SETUIDGID={{ _alias.s6_setuidgid }}
S6_SVSCAN={{ _alias.s6_svscan }}

for SVC in $(${LS} {{ dir }}/init); do
    if [ ! -d {{ dir }}/init/${SVC} ]; then
        ${RM} -rf {{ dir }}/init/${SVC}
    else
        ${ECHO} ${SVC} configuration is up to date.
    fi
done

${CHOWN} -R {{ treadmillid }} {{ dir }}

export PATH=${S6}/bin:${PATH}

# Starting svscan
exec \
    ${IONICE} -c2 -n0 \
    ${S6_ENVDIR} {{ dir }}/env \
    {{ treadmill }}/bin/treadmill sproc --cell - \
        exec -- \
            ${PID1} -i -p -m \
            ${S6_SETUIDGID} {{ treadmillid }} \
            ${S6_SVSCAN} {{ dir }}/init
