#!/bin/bash

sudo mount --make-rprivate /
adduser treadmld
export PYTHON_EGG_CACHE=/tmp/.python-eggs
echo 'Provisioned!'
