#!/bin/bash

cd $(mkdtemp -d)

# Make sure we have the dev tools
yum -y groupinstall "Development Tools"

# Just in case you started installing dependencies from yum
yum -y remove libnfnetlink

# lets put the source code here
mkdir -p ~/.src
cd ~/.src

# download and install the conntrack dependencies

# libnfnetlink
wget http://netfilter.org/projects/libnfnetlink/files/libnfnetlink-1.0.1.tar.bz2
tar xvfj libnfnetlink-1.0.1.tar.bz2
cd libnfnetlink-1.0.1
./configure && make && make install
cd ..

# libmnl
wget http://netfilter.org/projects/libmnl/files/libmnl-1.0.3.tar.bz2
tar xvjf libmnl-1.0.3.tar.bz2
cd libmnl-1.0.3
./configure && make && make install
cd ..

# libnetfilter
wget http://netfilter.org/projects/libnetfilter_conntrack/files/libnetfilter_conntrack-1.0.4.tar.bz2
tar xvjf libnetfilter_conntrack-1.0.4.tar.bz2
cd libnetfilter_conntrack-1.0.4
./configure PKG_CONFIG_PATH=/usr/local/lib/pkgconfig && make && make install
cd ..

# libnetfilter_cttimeout
wget http://netfilter.org/projects/libnetfilter_cttimeout/files/libnetfilter_cttimeout-1.0.0.tar.bz2
tar xvjf libnetfilter_cttimeout-1.0.0.tar.bz2
cd libnetfilter_cttimeout-1.0.0
./configure PKG_CONFIG_PATH=/usr/local/lib/pkgconfig && make && make install
cd ..

# libnetfilter_cthelper
wget http://netfilter.org/projects/libnetfilter_cthelper/files/libnetfilter_cthelper-1.0.0.tar.bz2
tar xvfj libnetfilter_cthelper-1.0.0.tar.bz2
cd libnetfilter_cthelper-1.0.0
./configure PKG_CONFIG_PATH=/usr/local/lib/pkgconfig && make && make install
cd ..

# libnetfilter_queue
wget http://netfilter.org/projects/libnetfilter_queue/files/libnetfilter_queue-1.0.2.tar.bz2
tar xvjf libnetfilter_queue-1.0.2.tar.bz2
cd libnetfilter_queue-1.0.2
./configure PKG_CONFIG_PATH=/usr/local/lib/pkgconfig && make && make install
cd ..

# Conntrack-tools
wget http://www.netfilter.org/projects/conntrack-tools/files/conntrack-tools-1.4.2.tar.bz2
tar xvjf conntrack-tools-1.4.2.tar.bz2
cd conntrack-tools-1.4.2
./configure PKG_CONFIG_PATH=/usr/local/lib/pkgconfig && make && make install

