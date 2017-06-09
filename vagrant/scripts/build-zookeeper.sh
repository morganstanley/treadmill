#!/bin/sh -e

cd $(mktemp -d)

if [ ! -e /etc/yum.repos.d/cloudera-cdh5.repo ]; then
    wget https://archive.cloudera.com/cdh5/redhat/5/x86_64/cdh/cloudera-cdh5.repo?_ga=2.172934241.314812559.1496985621-1968320782.1496291714 -O /etc/yum.repos.d/cloudera-cdh5.repo
fi

yum -y install zookeeper

cd /etc/zookeeper/conf
if [ ! -e zoo.cfg ]; then
    ln -s zoo_sample.cfg zoo.cfg
else
    echo zoo.cfg already exists.
fi

