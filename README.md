# Treadmill

[![Build Status](https://travis-ci.org/ThoughtWorksInc/treadmill.svg?branch=master)](https://travis-ci.org/ThoughtWorksInc/treadmill)

## Vagrant setup for development

### Prerequisites
* [VirtualBox](https://www.virtualbox.org/wiki/Downloads)
* [Vagrant](https://www.vagrantup.com/docs/installation/)
* Install the [Guest Additions plugin](https://github.com/dotless-de/vagrant-vbguest) for Vagrant
``` sh
vagrant plugin install vagrant-vbguest
```
### Vagrant Setup
* Clone the [treadmill](https://github.com/ThoughtWorksInc/treadmill.git) repo.
* Clone the [treadmill-pid1](https://github.com/Morgan-Stanley/treadmill-pid1) repo.
* Run the following commands
``` sh
cd treadmill
git checkout standard_setup
vagrant up
vagrant ssh
```
* Create the cgroup folders as root
``` sh
sudo su -
cd /sys/fs/cgroup
for i in *; do mkdir -p $i/treadmill/apps $i/treadmill/core $i/system ; done
cd -
```
* Start the zookeeper service
``` sh
cd /home/centos && zookeeper-3.4.9/bin/zkServer.sh start
```
* Make the mount private
``` sh
sudo mount --make-rprivate /
```
* Treadmill should now be available on the box
``` sh
source /home/centos/env/bin/activate
treadmill --help
```
