#!/bin/sh

ECHO={{ echo }}
RM={{ rm }}

$ECHO "########################################################################"
$ECHO "Cleanup all local scripts"
$RM -vf {{ dir }}/bin/*

# Reconfigure all scripts.
$ECHO "########################################################################"
$ECHO "Re-apply Treadmill template"
{{ treadmill }}/bin/treadmill sproc \
    --cell {{ cell }} \
    --zookeeper {{ zookeeper }} \
    --ldap {{ ldap }} \
    --ldap-search-base {{ ldap_search_base }} \
        install \
            --config $SCRIPTDIR/etc/linux.exe.config \
            --config $SCRIPTDIR/etc/linux.ms.exe.config \
            --config $SCRIPTDIR/../local/node.config.yml \
            node --install-dir {{ dir }}

exec "{{ dir }}/bin/upgrade.sh"

