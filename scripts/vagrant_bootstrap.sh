#!/bin/bash

sudo mount --make-rprivate /
adduser treadmld
echo 'password' > /home/treadmld/.treadmill_ldap
service slapd start
/home/centos/zookeeper-3.4.9/bin/zkServer.sh start
export PYTHON_EGG_CACHE=/tmp/.python-eggs
source /home/centos/treadmill/scripts/env_vars.sh
