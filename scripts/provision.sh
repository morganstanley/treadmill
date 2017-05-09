#!/bin/bash -e
sudo mount --make-rprivate /

id -u treadmld &>/dev/null || useradd treadmld

export PYTHON_EGG_CACHE=/tmp/.python-eggs

echo 'compiling pid1'
cd /home/centos/treadmill-pid1; make; cd -
