#!/bin/bash -e

echo Installing node packages.

yum -y install conntrack-tools.x86_64
yum -y install iproute
yum -y install libcgroup
yum -y install libcgroup-tools
yum -y install bridge-utils
yum -y install rrdtool-devel.x86_64

echo -e 'SELINUX=permissive\nSELINUXTYPE=targeted\n' >/etc/sysconfig/selinux
/sbin/setenforce 0
