#!/bin/sh

exec /opt/zookeeper-3.4.9/bin/zkServer.sh start-foreground \
    {{ dir }}/treadmill/conf/zoo.cfg
