Treadmill on AWS
==========================================================

Clone the treadmill repo and start the vagrant box:
::

  cd treadmill/vagrant
  vagrant up master

SSH in the vagrant machine:
::

  vagrant ssh master

Activate the virtual environment:
::

  source /opt/treadmill/bin/activate

Virtual environment should have treadmill installed. List the treadmill options:
::

  treadmill --help

----------------------------------------------------------

Set AWS Credentials and Region
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Assuming a user is present on AWS Account having AmazonEC2FullAccess, AmazonVPCFullAccess and AmazonRoute53FullAccess, there are two ways to set the credentials and region:

Either export them:

::

  export AWS_ACCESS_KEY_ID=<Access Key ID>
  export AWS_SECRET_ACCESS_KEY=<Secret Access Key>
  export AWS_DEFAULT_REGION=<aws_region>

Or create a credentials file ``~/.aws/credentials`` with following content:

::

  [default]
  aws_access_key_id=<access_key_id>
  aws_secret_access_key=<secret_access_key>
  region=us-east-1

----------------------------------------------------------


List treadmill AWS commands
::

  treadmill cloud --help

----------------------------------------------------------

Initialize VPC
^^^^^^^^^^^^^^

::

  treadmill cloud init

This creates a VPC, Internet Gateway, Security Group and Route53 Hosted Zone. Default values are used to create these resources. The values can be overwritten from command line.

List the options:

::

  treadmill cloud init --help


Initialize Domain
^^^^^^^^^^^^^^^^^

::

  treadmill cloud init-domain --vpc-id <vpc_id> --key <key_name> --image-id <ami_id> --ipa-admin-password <password>

ipa-admin-password should be at least 8 characters long.

Other values can be overwritten if required.

This will create IPA Server.


Initialize LDAP
^^^^^^^^^^^^^^^

LDAP can be initialized either along with cell or using the LDAP CLI. By default the cell initialization will create LDAP.

::

  treadmill cloud init-ldap --vpc-id <vpc_id> --key <key_name> --image-id <ami_id>

This will setup LDAP Server.


Initialize Cell
^^^^^^^^^^^^^^^

::

  treadmill cloud init-cell --vpc-id <vpc_id> --key <key_name> --image-id <ami_id> --without-ldap

This will setup 3 masters and 3 zookeeper boxes by default.

At this point all the hosts will be registered with IPA server.

