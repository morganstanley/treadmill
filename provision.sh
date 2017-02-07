#!/bin/bash -e

yum -y update
yum -y install java wget git

#treadmill services deps
yum -y install ipset iptables bridge-utils libcgroup-tools lvm2*

# treadmill build deps
yum -y group install "Development Tools"
yum -y install python-devel libkrb5-dev ntp krb5-server krb5-libs krb5-devel


# treadmill code
git clone https://github.com/Morgan-Stanley/treadmill.git
git clone https://github.com/Morgan-Stanley/treadmill-pid1.git
curl "https://bootstrap.pypa.io/get-pip.py" -o "get-pip.py"
python get-pip.py
pip install virtualenv
cd treadmill && virtualenv env
source env/bin/activate
git checkout remotes/origin/standard_setup
pip install --upgrade -r requirements.txt
python setup.py install
treadmill --help
cd -
cd treadmill-pid1 && make && cd -
# udpate pid1 path in treadmill/etc/linux.exe.config

# s6 builds

git clone git://git.skarnet.org/skalibs
cd skalibs && ./configure && make && sudo make install && cd -

git clone git://git.skarnet.org/execline 
cd execline && ./configure && make && sudo make install && cd -

git clone https://github.com/skarnet/s6.git
cd s6 && ./configure && make && sudo make install && cd -
# update s6 paths in treadmill/etc/linux.exe.config -- s6 variable takes s6 path /usr/bin/s6

#zookeeper build
wget http://apache.claz.org/zookeeper/stable/zookeeper-3.4.9.tar.gz
tar -xvzf zookeeper-3.4.9.tar.gz
cp zookeeper-3.4.9/conf/zoo_sample.cfg zookeeper-3.4.9/conf/zoo.cfg
zookeeper-3.4.9/bin/zkServer.sh start
zookeeper-3.4.9/bin/zkServer.sh status

# env vars
echo 'export TREADMILL_ZOOKEEPER=zookeeper://foo@127.0.0.1:2181' >> ~/.bash_profile
echo 'export TREADMILL_EXE_WHITELIST=/home/centos/treadmill/etc/linux.exe.config' >> ~/.bash_profile
echo 'export TREADMILL_CELL=ec2-34-198-157-255.compute-1.amazonaws.com' >> ~/.bash_profile
echo 'export TREADMILL_APPROOT=/tmp/treadmill' >> ~/.bash_profile
#export TREADMILL_DNS_DOMAIN=treadmill.com
#export TREADMILL_LDAP_SEARCH_BASE=foo
echo 'alias z=/home/centos/zookeeper-3.4.9/bin/zkCli.sh' >> ~/.bash_profile

#patches
# logging -- standard logging templates
cp /home/centos/treadmill/etc/logging /home/centos/treadmill/env/lib/python2.7/etc/

sudo mount --make-rprivate /
mkdir -p /tmp/treadmill/etc
cp /etc/resolv.conf /tmp/treadmill/etc/

#localDisk Image
dd if=/dev/zero of=/tmp/treadmill/treadmill.img seek=$((1024*1024*20)) count=1

#cgroup folders
cd /sys/fs/cgroup
for i in *; do mkdir -p $i/treadmill/apps $i/treadmill/core $i/system ; done #why again?
cd -

