#!/bin/bash

echo 'password' > /home/treadmld/.treadmill_ldap
/home/centos/zookeeper-3.4.9/bin/zkServer.sh start

sudo service slapd start

echo 'master provisioned!'
