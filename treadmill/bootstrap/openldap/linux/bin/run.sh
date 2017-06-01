#!/bin/sh

MKDIR={{ mkdir }}
RM={{ rm }}
MV={{ mv }}
ECHO={{ echo }}

if [[ ! -d '{{ dir_config }}/cn=config' ]]
then
    $MKDIR -p {{ dir }}/run
    $MKDIR -p {{ dir }}/openldap-data

    {{ slapadd }} -F {{ dir_config }} \
        -n 0 -l {{ dir_config }}/slapd.ldif -d -1
    {{ slapadd }} -F {{ dir_config }} \
        -n 0 -l {{ dir_config }}/schema/treadmill.ldif -d -1

    if [[ "$?" != 0 ]]
    then
        $RM -rvf '{{ dir_config }}/cn=config'
        $ECHO ERROR - slapadd failed. exiting.
        exit 1
    fi
fi

exec {{ slapd }} \
    -h {{ uri }} -F {{ dir_config }} \
{%- for log_level in log_levels %}
    -d {{ log_level }} \
{%- endfor %}
