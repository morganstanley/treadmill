#!/bin/sh

# Start root supervisor.

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

function add_svc {
    echo Adding service: $1 $2
    mkdir -p /tmp/init/$1
    rm -f /tmp/init/$1/run
    echo '#!/bin/sh'  > /tmp/init/$1/run
    echo exec $2     >> /tmp/init/$1/run
    chmod +x /tmp/init/$1/run
    /opt/s6/bin/s6-svscanctl -an /tmp/init
}

function del_svc {
    echo Deleting service: $1
    rm -rf /tmp/init/$1
    /opt/s6/bin/s6-svscanctl -an /tmp/init
}

# Source environment variables.
SCRIPTDIR=$(cd $(dirname $0) && pwd)

nohup $SCRIPTDIR/run_init.sh &

source $SCRIPTDIR/env_vars.sh

TM=/opt/treadmill/bin/treadmill

echo installing openldap

del_svc openldap

$TM admin install --install-dir /var/tmp/treadmill-openldap \
    openldap \
    --owner treadmld \
    --uri ldap://master:22389 \
    --suffix dc=local \
    --rootpw $(/usr/sbin/slappasswd -s secret)

add_svc openldap /var/tmp/treadmill-openldap/bin/run.sh

sleep 3

echo initializing openldap
$TM admin ldap init
$TM admin ldap schema --update

echo configuring local cell
$TM admin ldap cell configure local --version 0.1 --root /opt/treadmill \
    --username treadmld \
    --location local.local \

# For simplicity, use default zookeeper port - 2181. This way default
# install of zookeeper tools will just work.
# 
# This is single node Zookeeper install, no need to specify additional
# ports.
$TM admin ldap cell insert local --idx 1 --hostname master \
    --client-port 2181

# Add server to the cell.
$TM admin ldap server configure node --cell local

echo starting zookeper

del_svc zookeeper

$TM --outfmt yaml admin ldap cell configure local | $TM admin install \
    --install-dir /var/tmp/treadmill-zookeeper --config - zookeeper \
    --master-id 1

add_svc zookeeper /var/tmp/treadmill-zookeeper/treadmill/bin/run.sh

echo start master

del_svc master

$TM --outfmt yaml admin ldap cell configure local | $TM admin install \
    --install-dir /var/tmp/treadmill-master --config - master \
    --master-id 1 \
    --ldap-pwd secret

add_svc master /var/tmp/treadmill-master/treadmill/bin/run.sh
