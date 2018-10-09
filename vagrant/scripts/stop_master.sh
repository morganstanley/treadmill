#!/bin/sh

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

/opt/s6/bin/s6-svscanctl -q /tmp/init
