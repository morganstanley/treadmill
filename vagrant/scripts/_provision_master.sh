#!/bin/bash

SCRIPTDIR=$(cd $(dirname $0) && pwd)

mount --make-rprivate /

mkdir -p ~/.provision

function run {
    checksum=~/.provision/$(basename $1)
    md5sum -c $checksum
    if [ $? -eq 0 ]; then
        echo $1 is up to date.
    else
        $1 || (echo $1 failed. && exit 1)
        md5sum $1 > $checksum
    fi
}

run $SCRIPTDIR/install-base.sh 
run $SCRIPTDIR/install-ldap.sh
run $SCRIPTDIR/create-users.sh 
run $SCRIPTDIR/build-s6.sh 
run $SCRIPTDIR/build-zookeeper.sh 
run $SCRIPTDIR/build-pid1.sh 
run $SCRIPTDIR/venv.sh
run $SCRIPTDIR/configure-etc-hosts.sh
run $SCRIPTDIR/configure-profile.sh

$SCRIPTDIR/start_master_components.sh

echo 'master provisioned!'
