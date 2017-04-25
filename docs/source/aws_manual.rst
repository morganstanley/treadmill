Treadmill on AWS
==========================================================

List treadmill AWS commands
::

  treadmill aws --help

----------------------------------------------------------

Initialize
^^^^^^^^^^

Initialize default dirs for AWS:
::

  treadmill aws init

This creates deploy directory current directory. Make changes to benefit.

----------------------------------------------------------

Create a Deployment Manifest
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Edit *deploy/aws.yml*:

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


Edit *deploy/treadmill.yml*

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
Export AWS security credentials

::

  export AWS_ACCESS_KEY_ID=<Access Key ID>
  export AWS_SECRET_ACCESS_KEY=<Secret Access Key>

----------------------------------------------------------

Create/Destroy Treadmill Cell
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
**Create:**

::

  treadmill aws cell --create --key-file <path/to/pem/file>

  --playbook      default: deploy/cell.yml
  --inventory     default: deploy/controller.inventory
  --aws-config    default: deploy/config/aws.yml

**Destroy:**

::

  treadmill aws cell --destroy

  --playbook      default: deploy/destroy-cell.yml
  --inventory     default: deploy/controller.inventory
  --aws-config    default: deploy/config/aws.yml

----------------------------------------------------------

Create Node
^^^^^^^^^^^

Provision Node-Server in treadmill CELL on AWS

::

  treadmill aws node --create --key-file <path/to/pem/file>

  --playbook      default: deploy/node.yml
  --inventory     default: deploy/controller.inventory
  --aws-config    default: deploy/config/aws.yml
