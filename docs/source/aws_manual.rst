Treadmill on AWS
==========================================================

Assuming a CentOS 7 box(vagrant/local machine) install the treadmill binary:
::
  sudo yum install -y epel-release && sudo yum install -y python34
  sudo curl -L https://github.com/ThoughtWorksInc/treadmill/releases/download/0.1.0/treadmill -o /usr/bin/treadmill && sudo chmod +x /usr/bin/treadmill

List treadmill AWS commands
::

  treadmill aws --help

----------------------------------------------------------

Initialize
^^^^^^^^^^

Initialize default dirs for AWS:
::

  treadmill aws init

This creates deploy directory in the current directory. Make changes to benefit.

----------------------------------------------------------

Create a Key Pair
^^^^^^^^^^^^^^^^^
Create a key pair in aws console under EC2 Service and download the pem file required to ssh into master/node boxes.

Update a Deployment Manifest
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Edit *deploy/config/aws.yml*:

+-----------------------+----------------------------------------+
| Key                   | Value                                  |
+=======================+========================================+
| aws_key_name          | SSH key for ec2 instances              |
+-----------------------+----------------------------------------+
| ami_id                | EC2 AMI ID (defaults to Centos 7)      |
+-----------------------+----------------------------------------+
| region                | AWS Region to create cell              |
+-----------------------+----------------------------------------+
| az                    | Availability Zone in the region        |
+-----------------------+----------------------------------------+


Edit *deploy/config/treadmill.yml*

+-----------------------+----------------------------------------+
| Key                   | Value                                  |
+=======================+========================================+
| exact_count           | Number of instances to spin up for     |
|                       | master and node. By default it will    |
|                       | create a 3-master cluster and 1 node.  |
+-----------------------+----------------------------------------+

Other default values can also be changed if required.

----------------------------------------------------------


Set AWS Credentials
^^^^^^^^^^^^^^^^^^^
Assuming a user is present on AWS Account having AmazonEC2FullAccess, AmazonVPCFullAccess and AmazonRoute53FullAccess:

Export AWS security credentials

::

  export AWS_ACCESS_KEY_ID=<Access Key ID>
  export AWS_SECRET_ACCESS_KEY=<Secret Access Key>

----------------------------------------------------------

Create Treadmill Cell
^^^^^^^^^^^^^^^^^^^^^

::

  treadmill aws cell --create --with-freeipa --key-file <path/to/pem/file>

  --playbook      default: deploy/cell.yml
  --inventory     default: deploy/controller.inventory
  --aws-config    default: deploy/config/aws.yml
  --with-freeipa  default: no-freeipa

This will create 1 freeipa server, 3 masters and 1 node in the cell(vpc).
All the master and node services should be running.

SSH and Schedule an App
^^^^^^^^^^^^^^^^^^^^^^^
SSH in master/node using the downloaded pem file

**ssh**

::

  ssh -i <path/to/pem/file> centos@<master/node>_ip

**schedule**

::

  sudo su -
  treadmill admin master app schedule --env prod --proid treadmld --manifest <manifest_file> treadmld.foo


----------------------------------------------------------

Create Node
^^^^^^^^^^^

Provision Node-Server in treadmill CELL on AWS

::

  treadmill aws node --create --key-file <path/to/pem/file>

  --playbook      default: deploy/node.yml
  --inventory     default: deploy/controller.inventory
  --aws-config    default: deploy/config/aws.yml


Destroy Treadmill Cell
^^^^^^^^^^^^^^^^^^^^^^

::

  treadmill aws cell --destroy

  --playbook      default: deploy/destroy-cell.yml
  --inventory     default: deploy/controller.inventory
  --aws-config    default: deploy/config/aws.yml
