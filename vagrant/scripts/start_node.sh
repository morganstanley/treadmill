#!/bin/sh

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

mount --make-rprivate /

# Source environment variables.
SCRIPTDIR=$(cd $(dirname $0) && pwd)

source $SCRIPTDIR/env_vars.sh

/opt/treadmill/bin/treadmill --outfmt yaml admin ldap cell configure local | \
    /opt/treadmill/bin//treadmill admin install \
    --install-dir /var/tmp/treadmill --config - node

cd /tmp
nohup /var/tmp/treadmill/bin/run.sh &

