# Treadmill

[![Build Status](https://travis-ci.org/ThoughtWorksInc/treadmill.svg?branch=master)](https://travis-ci.org/ThoughtWorksInc/treadmill)

## Vagrant setup for development
### Prerequisites
* [Vagrant](https://www.vagrantup.com/docs/installation/)
* VirtualBox with guest additions plugin

### Vagrant Setup
* Clone the [treadmill](https://github.com/ThoughtWorksInc/treadmill.git) repo.
* Clone the [treadmill-pid1](https://github.com/Morgan-Stanley/treadmill-pid1) repo.
* Run the following commands
~~~~
cd treadmill
git checkout standard_setup
vagrant up
vagrant ssh
~~~~
Create the cgroup folders as root
~~~~
sudo su -
cd /sys/fs/cgroup
for i in *; do mkdir -p $i/treadmill/apps $i/treadmill/core $i/system ; done
cd -
~~~~
Start the zookeeper service
~~~~
cd /home/centos && zookeeper-3.4.9/bin/zkServer.sh start
~~~~
The box should now be ready to start the treadmill services.