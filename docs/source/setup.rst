Vagrant
=========================================================================

Prerequisites
^^^^^^^^^^^^^

- VirtualBox_
- Vagrant_
- Install the `Guest Additions Plugin`_ for Vagrant

::

	vagrant plugin install vagrant-vbguest

-------------------------------------------------------------------------

Setup
^^^^^^^^^^^^^

- Clone the treadmill_ repo.
- Clone the treadmill_pid1_ repo.
- Run the following commands

::

	cd treadmill
	git checkout standard_setup
	vagrant up
	vagrant ssh

- Create the cgroup folders as root

::

	sudo su
	cd /sys/fs/cgroup
	for i in *; do mkdir -p $i/treadmill/apps $i/treadmill/core $i/system ; done
	cd -

- Start the zookeeper service

::

	cd /home/centos && zookeeper-3.4.9/bin/zkServer.sh start

- Make the mount private

::

	sudo mount --make-rprivate /

- Treadmill should now be available on the box

::

	source /home/centos/env/bin/activate
	treadmill --help

.. _VirtualBox: https://www.virtualbox.org/wiki/Downloads
.. _Vagrant: https://www.vagrantup.com/docs/installation/
.. _Guest Additions Plugin: https://github.com/dotless-de/vagrant-vbguest
.. _treadmill: https://github.com/ThoughtWorksInc/treadmill.git 
.. _treadmill_pid1: https://github.com/Morgan-Stanley/treadmill-pid1
