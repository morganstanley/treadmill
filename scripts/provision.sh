#!/bin/bash -e

yum -y update
yum -y install java wget git

#treadmill services deps
yum -y install ipset iptables bridge-utils libcgroup-tools lvm2*

# treadmill build deps
yum -y group install "Development Tools"
yum -y install python-devel ntp krb5-server krb5-libs krb5-devel
yum -y install epel-release
yum -y install python34 python34-devel mercurial openssl-devel

curl "https://bootstrap.pypa.io/get-pip.py" -o /tmp/get-pip.py
python /tmp/get-pip.py
pip install virtualenv
cd /home/centos && virtualenv env
source env/bin/activate && cd -
cd /home/centos/treadmill
pip install --upgrade -r requirements.txt
python setup.py install
treadmill --help && cd -
cd /home/centos/treadmill-pid1 && make && cd -
# udpate pid1 path in treadmill/etc/linux.exe.config

# s6 builds
/home/centos/treadmill/scripts/s6_setup.sh
# update s6 paths in treadmill/etc/linux.exe.config -- s6 variable takes s6 path /usr/bin/s6

#zookeeper setup
/home/centos/treadmill/scripts/zk_setup.sh

#patches
mkdir -p /home/centos/env/lib/python2.7/etc
cp -rf /home/centos/treadmill/etc/logging /home/centos/env/lib/python2.7/etc/

sudo mount --make-rprivate /
mkdir -p /tmp/treadmill/etc
cp /etc/resolv.conf /tmp/treadmill/etc/

#localDisk Image
dd if=/dev/zero of=/tmp/treadmill/treadmill.img seek=$((1024*1024*20)) count=1

#cgroup folders
cd /sys/fs/cgroup
for i in *; do mkdir -p $i/treadmill/apps $i/treadmill/core $i/system ; done #why again?
cd -
