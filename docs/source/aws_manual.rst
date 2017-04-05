Deploy Treadmill on AWS
==========================================================

See all AWS commands for treadmill
::

  treadmill aws --help

----------------------------------------------------------

Initialize
^^^^^^^^^^

To make changes to ansible code and aws configuration run the following command:
::

  treadmill aws init

This will create the deploy directory in your current directory.

----------------------------------------------------------

Create a Deployment Manifest
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Replace the values in *deploy/aws.yml*:

+-----------------------+----------------------------------------+
| Key                   | Value                                  |
+=======================+========================================+
| aws_key_name          | SSH key for ec2 instances              |
+-----------------------+----------------------------------------+
| ami_id                | AMI ID for ec2 instances (Centos 7)    |
+-----------------------+----------------------------------------+
| region                | AWS Region to create cell              |
+-----------------------+----------------------------------------+
| az                    | Availability Zone in the region        |
+-----------------------+----------------------------------------+
| exact_count           | Number of instances to spin up for     |
|                       | master and node. By default it will    |
|                       | create a 3-master cluster and 1 node.  |
+-----------------------+----------------------------------------+

Other values in the config files can be changed if required.

----------------------------------------------------------

Set AWS Credentials
^^^^^^^^^^^^^^^^^^^
Export the aws security credentials

::

  export AWS_ACCESS_KEY_ID=<Access Key ID>
  export AWS_SECRET_ACCESS_KEY=<Secret Access Key>
----------------------------------------------------------

Create/Destroy Treadmill Cell
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Run the following command to create/destroy a cell in aws:

**Create:**

::

  treadmill aws cell --create --key-file <private_key_path>

**Destroy:**

::

  treadmill aws cell --destroy

We can override the playbook to be executed, inventory file, and the config files by using the additional options.

**For Ex:**

::

  treadmill aws cell --create --playbook cell.yml --inventory controller.inventory --key-file {{key_path}}/{{key_name}}.pem --aws-config aws.yml

----------------------------------------------------------

Create Node
^^^^^^^^^^^

Provision a node in treadmill CELL on AWS

::

  treadmill aws node --create --key-file <private_key_path>
