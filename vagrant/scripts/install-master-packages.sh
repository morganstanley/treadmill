#!/bin/bash

set -e

echo Installing master packages.

yum -y install policycoreutils-python

# Disable SELinux until we figure out services start
echo -e 'SELINUX=permissive\nSELINUXTYPE=targeted\n' >/etc/sysconfig/selinux
/sbin/setenforce 0
