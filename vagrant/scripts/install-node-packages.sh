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

if [ ! -e /etc/yum.repos.d/treadmill.repo ]; then
    curl -L https://s3.amazonaws.com/yum_repo_dev/treadmill.repo -o /etc/yum.repos.d/treadmill.repo
fi

# Install S6, pid1 and zookeeper
yum install s6 execline treadmill-pid1 --nogpgcheck -y
