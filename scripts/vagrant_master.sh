#!/bin/bash

sudo mount --make-rprivate /
adduser treadmld
echo 'password' > /home/treadmld/.treadmill_ldap
/home/centos/zookeeper-3.4.9/bin/zkServer.sh start
export PYTHON_EGG_CACHE=/tmp/.python-eggs

sudo service slapd start

echo 'Provisioned!'
