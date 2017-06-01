#!/bin/bash -e

echo Installing node packages.

yum -y install conntrack-tools.x86_64
yum -y install iproute
yum -y install libcgroup
yum -y install libcgroup-tools
yum -y install bridge-utils
