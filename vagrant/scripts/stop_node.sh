#!/bin/sh

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

ps -ef | grep pid1 | grep /var/tmp/treadmill/init | \
    awk '{print $2}' | xargs kill -9 
