#!/bin/sh

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

set -e

function add_svc {
    echo Adding service: $1
    cp -v /home/vagrant/treadmill/vagrant/systemd/$1.service \
        /etc/systemd/system/

    /bin/systemctl daemon-reload
    /bin/systemctl enable $1.service --now
}

function del_svc {
    echo Deleting service: $1
    /bin/systemctl disable $1.service --now || /bin/true
    rm -vrf /etc/systemd/system/$1.service
    /bin/systemctl daemon-reload
}

# Source environment variables.
SCRIPTDIR=$(cd $(dirname $0) && pwd)

source $SCRIPTDIR/env_vars.sh

TM=/opt/treadmill/bin/treadmill

echo Extracting cell config

$TM --outfmt yaml admin ldap cell configure local >/var/tmp/cell_conf.yml

echo Installing Treadmill Node

del_svc treadmill-node

$TM admin install \
    --install-dir /var/tmp/treadmill-node \
    --install-dir /var/tmp/treadmill \
    --config /var/tmp/cell_conf.yml \
    node

add_svc treadmill-node
