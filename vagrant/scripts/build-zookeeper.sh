#!/bin/sh -e

cd $(mktemp -d)

yum -y install java

wget http://apache.org/dist/zookeeper/zookeeper-3.4.9/zookeeper-3.4.9.tar.gz

tar xvf zookeeper-3.4.9.tar.gz -C /opt

cd /opt/zookeeper-3.4.9/conf
if [ ! -e zoo.cfg ]; then
    ln -s zoo_sample.cfg zoo.cfg
else
    echo zoo.cfg already exists.
fi

/opt/zookeeper-3.4.9/bin/zkServer.sh start
