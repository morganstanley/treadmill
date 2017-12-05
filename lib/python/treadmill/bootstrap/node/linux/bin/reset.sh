#!/bin/sh

ECHO={{ _alias.echo }}
RM={{ _alias.rm }}

$ECHO "########################################################################"
$ECHO "Cleanup all local scripts"
$RM -vf {{ dir }}/bin/*

# Reconfigure all scripts.
$ECHO "########################################################################"
$ECHO "Re-apply Treadmill template"
{{ treadmill_bin }} sproc \
    --cell {{ cell }} \
    --zookeeper {{ zookeeper }} \
    --ldap {{ ldap }} \
    --ldap-suffix {{ ldap_suffix }} \
        install \
            --config $SCRIPTDIR/etc/linux.aliases \
            --config $SCRIPTDIR/../local/node.config.yml \
            node --install-dir {{ dir }}

exec "{{ dir }}/bin/upgrade.sh"
