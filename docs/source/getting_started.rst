Getting Started
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
	vagrant up --provision

-------------------------------------------------------------------------

Master
^^^^^^^^^^^^^
- At this time Zookeeper and OpenLDAP should be running on 2181 and 1389 ports respectively:

::

   vagrant ssh master
   sudo su
   cd /home/centos/treadmill
   source ../env/bin/activate
   treadmill admin install --profile vagrant master --master-id 1 --run

-------------------------------------------------------------------------

Node
^^^^^^^^^^^^^^

::

   vagrant ssh node
   sudo su
   cd /home/centos/treadmill
   source ../env/bin/activate
   treadmill admin install --profile vagrant node --run

-------------------------------------------------------------------------

Schedule an App (e.g. python webserver - port 8000 )
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

   treadmill admin master app schedule --env prod --proid treadmld --manifest deploy/manifest.yml treadmld.foo


-------------------------------------------------------------------------

Trace
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

   treadmill admin trace <appname>

-------------------------------------------------------------------------

Discovery
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

   treadmill admin discovery <appname> --check-state

-------------------------------------------------------------------------

SSH
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

   treadmill admin ssh <appname>

-------------------------------------------------------------------------


.. _VirtualBox: https://www.virtualbox.org/wiki/Downloads
.. _Vagrant: https://www.vagrantup.com/docs/installation/
.. _Guest Additions Plugin: https://github.com/dotless-de/vagrant-vbguest
.. _treadmill: https://github.com/Morgan-Stanley/treadmill
.. _treadmill_pid1: https://github.com/Morgan-Stanley/treadmill-pid1
