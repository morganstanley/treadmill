#!/bin/sh

set -e

# configure only if [[ ! -d {{ dir_config }}/cn=config ]] ?
if [[ ! -d '{{ dir_config }}/cn=config' ]]
then
    #
    # Import/init LDAP configuration
    #
    {{ _alias.slapadd }} \
        -F {{ dir_config }} \
        -n 0 \
        -l {{ dir_config }}/slapd.ldif \
        -d -1

    #
    # Import/init LDAP schemas
    #
    {{ _alias.slapadd }} \
        -F {{ dir_config }} \
        -n 0 \
        -l {{ dir_config }}/schema/treadmill.ldif \
        -d -1

fi

exit 0
