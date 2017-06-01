#!/bin/sh

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

mount --make-rprivate /

export PATH=$PATH:/opt/s6/bin
export LC_ALL=en_US.utf8
export LANG=en_US.utf8

mkdir -p /tmp/init
/opt/treadmill-pid1/bin/pid1 -m -p /opt/s6/bin/s6-svscan /tmp/init
