#!/bin/sh

exec /usr/lib/zookeeper/bin/zkServer.sh start-foreground \
    {{ dir }}/treadmill/conf/zoo.cfg
