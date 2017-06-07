#!/bin/bash

set -e

yum -y install openldap openldap-clients openldap-servers

# Enable 22389 port for LDAP (requires policycoreutils-python)
/sbin/semanage  port -a -t ldap_port_t -p tcp 22389
/sbin/semanage  port -a -t ldap_port_t -p udp 22389


