#!/bin/sh

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

set -e

# Source environment variables.
SCRIPTDIR=$(cd $(dirname $0) && pwd)

source $SCRIPTDIR/env_vars.sh

. $SCRIPTDIR/svc_utils.sh

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
