.. AUTO-GENERATED FILE - DO NOT EDIT!! Use `make cli_docs`.
==============================================================
CLI
==============================================================

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: run [OPTIONS] COMMAND [ARGS]...
		
		  Admin commands.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  blackout    Manage server and app blackouts.
		  checkout    Run interactive checkout.
		  cloud       Manage Treadmill on cloud
		  cron        Manage Treadmill cron jobs
		  diag        Local node and container diagnostics.
		  discovery   Discover container endpoints.
		  http        Invoke Treadmill HTTP REST API.
		  install     Installs Treadmill.
		  ldap        Manage Treadmill LDAP data
		  logs        View application's service logs.
		  master      Manage Treadmill master data
		  ok          Check status of Zookeeper ensemble.
		  postmortem  Collect Treadmill node data
		  scheduler   Report scheduler state.
		  show        Show Treadmill apps
		  ssh         SSH into Treadmill container.
		  trace       Trace application events.
		  wait        Wait for all instances to exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.blackout
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: blackout [OPTIONS] COMMAND [ARGS]...
		
		  Manage server and app blackouts.
		
		Options:
		  --cell TEXT  [required]
		  --help       Show this message and exit.
		
		Commands:
		  app     Manage app blackouts.
		  server  Manage server blackout.



		Usage: blackout app [OPTIONS]
		
		  Manage app blackouts.
		
		Options:
		  --app TEXT  App name to blackout.
		  --clear     Clear blackout.
		  --help      Show this message and exit.

		Usage: blackout server [OPTIONS]
		
		  Manage server blackout.
		
		Options:
		  --server TEXT  Server name to blackout.
		  --reason TEXT  Blackout reason.
		  --fmt TEXT     Format of the blackout output.
		  --clear        Clear blackout.
		  --help         Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.checkout
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: run [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...
		
		  Run interactive checkout.
		
		Options:
		  --cell TEXT  [required]
		  --verbose
		  --html
		  --help       Show this message and exit.
		
		Commands:
		  api       Checkout API.
		  capacity  Check cell capacity.
		  ldap      Checkout LDAP infra.
		  servers   Checkout nodeinfo API.
		  sysapps   Checkout system apps health.
		  zk        Check Zookeeper status.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.checkout.api
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: api [OPTIONS]
		
		  Checkout API.
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.checkout.capacity
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: capacity [OPTIONS]
		
		  Check cell capacity.
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.checkout.ldap
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: ldap [OPTIONS]
		
		  Checkout LDAP infra.
		
		Options:
		  --ldap-list LIST  [required]
		  --help            Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.checkout.servers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: servers [OPTIONS]
		
		  Checkout nodeinfo API.
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.checkout.sysapps
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: sysapps [OPTIONS]
		
		  Checkout system apps health.
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.checkout.zk
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: zk [OPTIONS]
		
		  Check Zookeeper status.
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.cloud
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: cloud [OPTIONS] COMMAND [ARGS]...
		
		  Manage Treadmill on cloud
		
		Options:
		  --domain TEXT  Domain for hosted zone  [required]
		  --help         Show this message and exit.
		
		Commands:
		  configure  Configure Treadmill EC2 Objects
		  delete     Delete Treadmill EC2 Objects
		  list       Show Treadmill Cloud Resources
		  port       enable/disable EC2 instance port



		Usage: cloud configure [OPTIONS] COMMAND [ARGS]...
		
		  Configure Treadmill EC2 Objects
		
		Options:
		  --proid TEXT  Proid user for treadmill  [default: treadmld]
		  --help        Show this message and exit.
		
		Commands:
		  cell    Configure Treadmill Cell
		  domain  Configure Treadmill Domain (IPA)
		  ldap    Configure Treadmill LDAP
		  node    Configure new Node in Cell
		  vpc     Configure Treadmill VPC

		Usage: cloud delete [OPTIONS] COMMAND [ARGS]...
		
		  Delete Treadmill EC2 Objects
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  cell    Delete Cell (Subnet)
		  domain  Delete IPA
		  ldap    Delete LDAP
		  node    Delete Node
		  vpc     Delete VPC

		Usage: cloud list [OPTIONS] COMMAND [ARGS]...
		
		  Show Treadmill Cloud Resources
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  cell  Show Cell
		  vpc   Show VPC(s)

		Usage: cloud port [OPTIONS] COMMAND [ARGS]...
		
		  enable/disable EC2 instance port
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  disable  Disable Port from my ip
		  enable   Enable Port from my ip



		Usage: configure cell [OPTIONS]
		
		  Configure Treadmill Cell
		
		Options:
		  --vpc-name TEXT            VPC Name  [required]
		  --key TEXT                 SSH Key Name  [required]
		  --image TEXT               Image to use for new instances e.g. RHEL-7.4
		                             [required]
		  --subnet-name TEXT         Cell(Subnet) Name  [required]
		  --count INTEGER            Number of Treadmill masters to spin up  [default:
		                             3]
		  --region TEXT              Region for the vpc
		  --name TEXT                Treadmill master name  [default: TreadmillMaster]
		  --instance-type TEXT       AWS ec2 instance type  [default: t2.micro]
		  --tm-release TEXT          Treadmill release to use
		  --app-root TEXT            Treadmill app root  [default: /var/tmp]
		  --cidr-block TEXT          CIDR block for the cell  [default: 172.23.0.0/24]
		  --ipa-admin-password TEXT  Password for IPA admin
		  -m, --manifest TEXT        Options YAML file.  NOTE: This argument is mutually
		                             exclusive with arguments: [ipa_admin_password,
		                             region, cell_subnet_name, cidr_block,
		                             instance_type, vpc_name, key, count, name,
		                             app_root, tm_release, image].
		  --help                     Show this message and exit.

		Usage: configure domain [OPTIONS]
		
		  Configure Treadmill Domain (IPA)
		
		Options:
		  --vpc-name TEXT            VPC Name  [required]
		  --key TEXT                 SSH key name  [required]
		  --image TEXT               Image to use for new master instance e.g. RHEL-7.4
		                             [required]
		  --subnet-name TEXT         Subnet Name  [required]
		  --name TEXT                Name of the instance  [default: TreadmillIPA]
		  --region TEXT              Region for the vpc
		  --subnet-cidr-block TEXT   Cidr block of subnet for IPA  [default:
		                             172.23.2.0/24]
		  --count INTEGER            Count of the instances  [default: 1]
		  --ipa-admin-password TEXT  Password for IPA admin
		  --tm-release TEXT          Treadmill Release
		  --instance-type TEXT       Instance type  [default: t2.medium]
		  -m, --manifest TEXT        Options YAML file.  NOTE: This argument is mutually
		                             exclusive with arguments: [ipa_admin_password,
		                             region, subnet_cidr_blocksubnet_name,
		                             instance_type, vpc_id, key, count, name,
		                             tm_release, image].
		  --help                     Show this message and exit.

		Usage: configure ldap [OPTIONS]
		
		  Configure Treadmill LDAP
		
		Options:
		  --vpc-name TEXT            VPC name  [required]
		  --key TEXT                 SSH Key Name  [required]
		  --name TEXT                LDAP Instance Name  [required]
		  --image TEXT               Image to use for instances e.g. RHEL-7.4
		                             [required]
		  --subnet-name TEXT         Subnet Name for LDAP  [required]
		  --region TEXT              Region for the vpc
		  --instance-type TEXT       AWS ec2 instance type  [default: t2.micro]
		  --tm-release TEXT          Treadmill release to use
		  --app-root TEXT            Treadmill app root  [default: /var/tmp]
		  --ldap-cidr-block TEXT     CIDR block for LDAP  [default: 172.23.1.0/24]
		  --ipa-admin-password TEXT  Password for IPA admin
		  -m, --manifest TEXT        Options YAML file.  NOTE: This argument is mutually
		                             exclusive with arguments: [region,
		                             ipa_admin_passwordldap_cidr_block, instance_type,
		                             vpc_name, key, name, subnet_name, app_root,
		                             tm_release, image].
		  --help                     Show this message and exit.

		Usage: configure node [OPTIONS]
		
		  Configure new Node in Cell
		
		Options:
		  --vpc-name TEXT            VPC Name  [required]
		  --key TEXT                 SSH Key Name  [required]
		  --image TEXT               Image to use for new node instance e.g. RHEL-7.4
		                             [required]
		  --subnet-name TEXT         Cell(Subnet) Name  [required]
		  --region TEXT              Region for the vpc
		  --name TEXT                Node name  [default: TreadmillNode]
		  --instance-type TEXT       AWS ec2 instance type  [default: t2.large]
		  --tm-release TEXT          Treadmill release to use
		  --app-root TEXT            Treadmill app root  [default: /var/tmp/treadmill-
		                             node]
		  --ipa-admin-password TEXT  Password for IPA admin
		  --with-api                 Provision node with Treadmill APIs  [default:
		                             False]
		  -m, --manifest TEXT        Options YAML file.  NOTE: This argument is mutually
		                             exclusive with arguments: [region,
		                             ipa_admin_passwordwith_api, instance_type,
		                             vpc_name, key, name, subnet_name, app_root,
		                             tm_release, image].
		  --help                     Show this message and exit.

		Usage: configure vpc [OPTIONS]
		
		  Configure Treadmill VPC
		
		Options:
		  --name TEXT            VPC name  [required]
		  --region TEXT          Region for the vpc
		  --vpc-cidr-block TEXT  CIDR block for the vpc  [default: 172.23.0.0/16]
		  -m, --manifest TEXT    Options YAML file.  NOTE: This argument is mutually
		                         exclusive with arguments: [vpc_cidr_block, name,
		                         region].
		  --help                 Show this message and exit.



		Usage: delete cell [OPTIONS]
		
		  Delete Cell (Subnet)
		
		Options:
		  --vpc-name TEXT     VPC Name  [required]
		  --subnet-name TEXT  Subnet Name of cell  [required]
		  --help              Show this message and exit.

		Usage: delete domain [OPTIONS]
		
		  Delete IPA
		
		Options:
		  --vpc-name TEXT     VPC Name  [required]
		  --subnet-name TEXT  Subnet Name of Domain  [required]
		  --name TEXT         Name of Instance  [default: TreadmillIPA]
		  --help              Show this message and exit.

		Usage: delete ldap [OPTIONS]
		
		  Delete LDAP
		
		Options:
		  --vpc-name TEXT     VPC Name  [required]
		  --subnet-name TEXT  Subnet Name of LDAP
		  --name TEXT         Name of Instance
		  --help              Show this message and exit.

		Usage: delete node [OPTIONS]
		
		  Delete Node
		
		Options:
		  --vpc-name TEXT     VPC Name  [required]
		  --name TEXT         Instance Name
		  --instance-id TEXT  Instance ID
		  --help              Show this message and exit.

		Usage: delete vpc [OPTIONS]
		
		  Delete VPC
		
		Options:
		  --vpc-name TEXT  VPC Name  [required]
		  --help           Show this message and exit.



		Usage: list cell [OPTIONS]
		
		  Show Cell
		
		Options:
		  --vpc-name TEXT     VPC Name
		  --subnet-name TEXT  Subnet Name of cell
		  --help              Show this message and exit.

		Usage: list vpc [OPTIONS]
		
		  Show VPC(s)
		
		Options:
		  --vpc-name TEXT  VPC Name
		  --help           Show this message and exit.



		Usage: port disable [OPTIONS]
		
		  Disable Port from my ip
		
		Options:
		  -a, --anywhere                From Anywhere?  [default: True]
		  --protocol TEXT               Protocol  [default: tcp]
		  -p, --port TEXT               Port  [required]
		  -s, --security-group-id TEXT  Security Group ID  [required]
		  --help                        Show this message and exit.

		Usage: port enable [OPTIONS]
		
		  Enable Port from my ip
		
		Options:
		  -a, --anywhere                From Anywhere?  [default: True]
		  --protocol TEXT               Protocol  [default: tcp]
		  -p, --port TEXT               Port  [required]
		  -s, --security-group-id TEXT  Security Group ID  [required]
		  --help                        Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.cron
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: cron_group [OPTIONS] COMMAND [ARGS]...
		
		  Manage Treadmill cron jobs
		
		Options:
		  --cell TEXT  [required]
		  --help       Show this message and exit.
		
		Commands:
		  configure  Create or modify an existing app start...
		  delete     Delete an app schedule
		  list       List out all cron events
		  pause      Pause a job ID
		  resume     Resume a job ID



^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.diag
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: diag [OPTIONS] COMMAND [ARGS]...
		
		  Local node and container diagnostics.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  psmem  Reports memory utilization details for given...



		Usage: diag psmem [OPTIONS] APP
		
		  Reports memory utilization details for given container.
		
		Options:
		  --fast         Disable statm/pss analysis.
		  -v, --verbose  Verbose
		  --percent
		  --help         Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.discovery
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: top [OPTIONS] APP [ENDPOINT]
		
		  Discover container endpoints.
		
		Options:
		  --cell TEXT       [required]
		  --zookeeper TEXT
		  --watch
		  --check-state
		  --separator TEXT
		  --help            Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.http
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: top [OPTIONS] COMMAND [ARGS]...
		
		  Invoke Treadmill HTTP REST API.
		
		Options:
		  --cell TEXT           [required]
		  --api TEXT            API url to use.
		  --outfmt [json|yaml]
		  --help                Show this message and exit.
		
		Commands:
		  delete  REST DELETE request.
		  get     REST GET request.
		  post    REST POST request.
		  put     REST PUT request.



		Usage: top delete [OPTIONS] PATH
		
		  REST DELETE request.
		
		Options:
		  --help  Show this message and exit.

		Usage: top get [OPTIONS] PATH
		
		  REST GET request.
		
		Options:
		  --help  Show this message and exit.

		Usage: top post [OPTIONS] PATH PAYLOAD
		
		  REST POST request.
		
		Options:
		  --help  Show this message and exit.

		Usage: top put [OPTIONS] PATH PAYLOAD
		
		  REST PUT request.
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.install
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: install [OPTIONS] COMMAND [ARGS]...
		
		  Installs Treadmill.
		
		Options:
		  --install-dir TEXT          Target installation directory.  [required]
		  --profile TEXT              Install profile.
		  --cell TEXT                 [required]
		  --config PATH
		  --override KEY/VALUE PAIRS
		  --help                      Show this message and exit.
		
		Commands:
		  haproxy    Installs Treadmill haproxy.
		  master     Installs Treadmill master.
		  node       Installs Treadmill node.
		  openldap   Installs Treadmill Openldap server.
		  spawn      Installs Treadmill spawn.
		  zookeeper  Installs Treadmill master.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.install.haproxy
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: haproxy [OPTIONS]
		
		  Installs Treadmill haproxy.
		
		Options:
		  --run / --no-run
		  --help            Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.install.master
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: master [OPTIONS]
		
		  Installs Treadmill master.
		
		Options:
		  --run / --no-run
		  --master-id [1|2|3]  [required]
		  --ldap-pwd TEXT      LDAP password (clear text of path to file).
		  --help               Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.install.node
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: node [OPTIONS]
		
		  Installs Treadmill node.
		
		Options:
		  --run / --no-run
		  --benchmark / --no-benchmark
		  --help                        Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.install.openldap
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: openldap [OPTIONS]
		
		  Installs Treadmill Openldap server.
		
		Options:
		  --gssapi                        use gssapi auth.
		  -p, --rootpw TEXT               password hash, generated by slappass -s <pwd>.
		  -o, --owner TEXT                root user.  [required]
		  --env TEXT                      Treadmill environment  [required]
		  -s, --suffix TEXT               suffix (e.g dc=example,dc=com).
		  -u, --uri TEXT                  uri, e.g: ldap://...:20389  [required]
		  -m, --masters LIST              list of masters.
		  --first-time / --no-first-time
		  --run / --no-run
		  --help                          Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.install.spawn
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: spawn [OPTIONS]
		
		  Installs Treadmill spawn.
		
		Options:
		  --run / --no-run
		  --treadmill-id TEXT  Treadmill admin user.
		  --help               Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.install.zookeeper
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: zookeeper [OPTIONS]
		
		  Installs Treadmill master.
		
		Options:
		  --run / --no-run
		  --master-id [1|2|3]  [required]
		  --help               Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.invoke
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: invoke [OPTIONS] COMMAND [ARGS]...
		
		  Directly invoke Treadmill API without REST.
		
		Options:
		  --authz TEXT
		  --cell TEXT   [required]
		  --help        Show this message and exit.
		
		Commands:
		  allocation      Treadmill Allocation REST api.
		  api-lookup      Treadmill API lookup API.
		  app             Treadmill App REST api.
		  app-group       Treadmill AppGroup REST api.
		  app-monitor     Treadmill AppMonitor REST api.
		  cell            Treadmill Cell REST api.
		  cloud           Treadmill Cloud REST API.
		  cron            Treadmill CRON REST api.
		  dns             Treadmill DNS REST api.
		  identity-group  Treadmill Identity Group REST api.
		  instance        Treadmill Instance REST api.
		  ipa             Treadmill IPA REST API.
		  local           Treadmill Local REST api.
		  nodeinfo        Treadmill Local REST api.
		  scheduler       Scheduler reports API.
		  server          Treadmill Server REST api.
		  tenant          Treadmill Tenant REST api.



		Usage: invoke allocation [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Allocation REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Create allocation.
		  delete  Delete allocation.
		  get     Get allocation configuration.
		  list    List allocations.
		  update  Update allocation.

		Usage: invoke api-lookup [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill API lookup API.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  get   No get method
		  list  Constructs a command handler.

		Usage: invoke app [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill App REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Create (configure) application.
		  delete  Delete configured application.
		  get     Get application configuration.
		  list    List configured applications.
		  update  Update application configuration.

		Usage: invoke app-group [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill AppGroup REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Create (configure) application.
		  delete  Delete configured application.
		  get     Get application configuration.
		  list    List configured applications.
		  update  Update application configuration.

		Usage: invoke app-monitor [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill AppMonitor REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Create (configure) application monitor.
		  delete  Delete configured application monitor.
		  get     Get application monitor configuration.
		  list    List configured monitors.
		  update  Update application configuration.

		Usage: invoke cell [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Cell REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Create cell.
		  delete  Delete cell.
		  get     Get cell configuration.
		  list    List cells.
		  update  Update cell.

		Usage: invoke cloud [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Cloud REST API.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  cells          Constructs a command handler.
		  configure      Constructs a command handler.
		  delete_cell    Constructs a command handler.
		  delete_ldap    Constructs a command handler.
		  delete_server  Constructs a command handler.
		  vpcs           Constructs a command handler.

		Usage: invoke cron [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill CRON REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Create cron job.
		  delete  Delete configured cron job.
		  get     Get cron job configuration.
		  list    List configured cron jobs.
		  update  Update cron job configuration.

		Usage: invoke dns [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill DNS REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  get   Get DNS server entry
		  list  List DNS servers

		Usage: invoke identity-group [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Identity Group REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Create (configure) application group.
		  delete  Delete configured application group.
		  get     Get application group configuration.
		  list    List configured identity groups.
		  update  Update application configuration.

		Usage: invoke instance [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Instance REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Create (configure) instance.
		  delete  Delete configured instance.
		  get     Get instance configuration.
		  list    List configured instances.
		  update  Update instance configuration.

		Usage: invoke ipa [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill IPA REST API.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  add_host     Constructs a command handler.
		  add_user     Constructs a command handler.
		  delete_host  Constructs a command handler.
		  delete_user  Constructs a command handler.
		  service_add  Constructs a command handler.

		Usage: invoke local [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Local REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  get   Get instance info.
		  list  List all instances on the node.

		Usage: invoke nodeinfo [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Local REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  get  Get hostname nodeinfo endpoint info.

		Usage: invoke scheduler [OPTIONS] COMMAND [ARGS]...
		
		  Scheduler reports API.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  get  Fetch report from ZooKeeper and return it as...

		Usage: invoke server [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Server REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Create server.
		  delete  Delete server.
		  get     Get server configuration.
		  list    List servers by cell and/or features.
		  update  Update server.

		Usage: invoke tenant [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Tenant REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Create tenant.
		  delete  Delete tenant.
		  get     Get tenant configuration.
		  list    List tenants.
		  update  Update tenant.



		Usage: allocation create [OPTIONS] RSRC_ID RSRC
		
		  Create allocation.
		
		Options:
		  --help  Show this message and exit.

		Usage: allocation delete [OPTIONS] RSRC_ID
		
		  Delete allocation.
		
		Options:
		  --help  Show this message and exit.

		Usage: allocation get [OPTIONS] RSRC_ID
		
		  Get allocation configuration.
		
		Options:
		  --help  Show this message and exit.

		Usage: allocation list [OPTIONS]
		
		  List allocations.
		
		Options:
		  --tenant_id TEXT
		  --help            Show this message and exit.

		Usage: allocation update [OPTIONS] RSRC_ID RSRC
		
		  Update allocation.
		
		Options:
		  --help  Show this message and exit.



		Usage: api-lookup get [OPTIONS]
		
		  No get method
		
		Options:
		  --help  Show this message and exit.

		Usage: api-lookup list [OPTIONS]
		
		  Constructs a command handler.
		
		Options:
		  --help  Show this message and exit.



		Usage: app create [OPTIONS] RSRC_ID RSRC
		
		  Create (configure) application.
		
		Options:
		  --help  Show this message and exit.

		Usage: app delete [OPTIONS] RSRC_ID
		
		  Delete configured application.
		
		Options:
		  --help  Show this message and exit.

		Usage: app get [OPTIONS] RSRC_ID
		
		  Get application configuration.
		
		Options:
		  --help  Show this message and exit.

		Usage: app list [OPTIONS]
		
		  List configured applications.
		
		Options:
		  --match TEXT
		  --help        Show this message and exit.

		Usage: app update [OPTIONS] RSRC_ID RSRC
		
		  Update application configuration.
		
		Options:
		  --help  Show this message and exit.



		Usage: app-group create [OPTIONS] RSRC_ID RSRC
		
		  Create (configure) application.
		
		Options:
		  --help  Show this message and exit.

		Usage: app-group delete [OPTIONS] RSRC_ID
		
		  Delete configured application.
		
		Options:
		  --help  Show this message and exit.

		Usage: app-group get [OPTIONS] RSRC_ID
		
		  Get application configuration.
		
		Options:
		  --help  Show this message and exit.

		Usage: app-group list [OPTIONS]
		
		  List configured applications.
		
		Options:
		  --match TEXT
		  --help        Show this message and exit.

		Usage: app-group update [OPTIONS] RSRC_ID RSRC
		
		  Update application configuration.
		
		Options:
		  --help  Show this message and exit.



		Usage: app-monitor create [OPTIONS] RSRC_ID RSRC
		
		  Create (configure) application monitor.
		
		Options:
		  --help  Show this message and exit.

		Usage: app-monitor delete [OPTIONS] RSRC_ID
		
		  Delete configured application monitor.
		
		Options:
		  --help  Show this message and exit.

		Usage: app-monitor get [OPTIONS] RSRC_ID
		
		  Get application monitor configuration.
		
		Options:
		  --help  Show this message and exit.

		Usage: app-monitor list [OPTIONS]
		
		  List configured monitors.
		
		Options:
		  --match TEXT
		  --help        Show this message and exit.

		Usage: app-monitor update [OPTIONS] RSRC_ID RSRC
		
		  Update application configuration.
		
		Options:
		  --help  Show this message and exit.



		Usage: cell create [OPTIONS] RSRC_ID RSRC
		
		  Create cell.
		
		Options:
		  --help  Show this message and exit.

		Usage: cell delete [OPTIONS] RSRC_ID
		
		  Delete cell.
		
		Options:
		  --help  Show this message and exit.

		Usage: cell get [OPTIONS] RSRC_ID
		
		  Get cell configuration.
		
		Options:
		  --help  Show this message and exit.

		Usage: cell list [OPTIONS]
		
		  List cells.
		
		Options:
		  --help  Show this message and exit.

		Usage: cell update [OPTIONS] RSRC_ID RSRC
		
		  Update cell.
		
		Options:
		  --help  Show this message and exit.



		Usage: cloud cells [OPTIONS] DOMAIN VPC_NAME CELL_NAME
		
		  Constructs a command handler.
		
		Options:
		  --help  Show this message and exit.

		Usage: cloud configure [OPTIONS] VPC_NAME DOMAIN NAME ARGS
		
		  Constructs a command handler.
		
		Options:
		  --help  Show this message and exit.

		Usage: cloud delete_cell [OPTIONS] VPC_NAME DOMAIN CELL_NAME
		
		  Constructs a command handler.
		
		Options:
		  --help  Show this message and exit.

		Usage: cloud delete_ldap [OPTIONS] VPC_NAME DOMAIN NAME
		
		  Constructs a command handler.
		
		Options:
		  --help  Show this message and exit.

		Usage: cloud delete_server [OPTIONS] VPC_NAME DOMAIN NAME
		
		  Constructs a command handler.
		
		Options:
		  --help  Show this message and exit.

		Usage: cloud vpcs [OPTIONS] DOMAIN VPC_NAME
		
		  Constructs a command handler.
		
		Options:
		  --help  Show this message and exit.



		Usage: cron create [OPTIONS] RSRC_ID RSRC
		
		  Create cron job.
		
		Options:
		  --help  Show this message and exit.

		Usage: cron delete [OPTIONS] RSRC_ID
		
		  Delete configured cron job.
		
		Options:
		  --help  Show this message and exit.

		Usage: cron get [OPTIONS] RSRC_ID
		
		  Get cron job configuration.
		
		Options:
		  --help  Show this message and exit.

		Usage: cron list [OPTIONS]
		
		  List configured cron jobs.
		
		Options:
		  --resource TEXT
		  --match TEXT
		  --help           Show this message and exit.

		Usage: cron update [OPTIONS] RSRC_ID RSRC
		
		  Update cron job configuration.
		
		Options:
		  --resume BOOLEAN
		  --pause BOOLEAN
		  --help            Show this message and exit.



		Usage: dns get [OPTIONS] RSRC_ID
		
		  Get DNS server entry
		
		Options:
		  --help  Show this message and exit.

		Usage: dns list [OPTIONS]
		
		  List DNS servers
		
		Options:
		  --help  Show this message and exit.



		Usage: identity-group create [OPTIONS] RSRC_ID RSRC
		
		  Create (configure) application group.
		
		Options:
		  --help  Show this message and exit.

		Usage: identity-group delete [OPTIONS] RSRC_ID
		
		  Delete configured application group.
		
		Options:
		  --help  Show this message and exit.

		Usage: identity-group get [OPTIONS] RSRC_ID
		
		  Get application group configuration.
		
		Options:
		  --help  Show this message and exit.

		Usage: identity-group list [OPTIONS]
		
		  List configured identity groups.
		
		Options:
		  --match TEXT
		  --help        Show this message and exit.

		Usage: identity-group update [OPTIONS] RSRC_ID RSRC
		
		  Update application configuration.
		
		Options:
		  --help  Show this message and exit.



		Usage: instance create [OPTIONS] RSRC_ID RSRC
		
		  Create (configure) instance.
		
		Options:
		  --created_by TEXT
		  --count INTEGER
		  --help             Show this message and exit.

		Usage: instance delete [OPTIONS] RSRC_ID
		
		  Delete configured instance.
		
		Options:
		  --deleted_by TEXT
		  --help             Show this message and exit.

		Usage: instance get [OPTIONS] RSRC_ID
		
		  Get instance configuration.
		
		Options:
		  --help  Show this message and exit.

		Usage: instance list [OPTIONS]
		
		  List configured instances.
		
		Options:
		  --match TEXT
		  --help        Show this message and exit.

		Usage: instance update [OPTIONS] RSRC_ID RSRC
		
		  Update instance configuration.
		
		Options:
		  --help  Show this message and exit.



		Usage: ipa add_host [OPTIONS] HOSTNAME
		
		  Constructs a command handler.
		
		Options:
		  --help  Show this message and exit.

		Usage: ipa add_user [OPTIONS] USERNAME
		
		  Constructs a command handler.
		
		Options:
		  --help  Show this message and exit.

		Usage: ipa delete_host [OPTIONS] HOSTNAME
		
		  Constructs a command handler.
		
		Options:
		  --help  Show this message and exit.

		Usage: ipa delete_user [OPTIONS] USERNAME
		
		  Constructs a command handler.
		
		Options:
		  --help  Show this message and exit.

		Usage: ipa service_add [OPTIONS] PROTOCOL SERVICE ARGS
		
		  Constructs a command handler.
		
		Options:
		  --help  Show this message and exit.



		Usage: local get [OPTIONS] UNIQID
		
		  Get instance info.
		
		Options:
		  --help  Show this message and exit.

		Usage: local list [OPTIONS]
		
		  List all instances on the node.
		
		Options:
		  --inc_svc BOOLEAN
		  --state TEXT
		  --help             Show this message and exit.



		Usage: nodeinfo get [OPTIONS] HOSTNAME
		
		  Get hostname nodeinfo endpoint info.
		
		Options:
		  --help  Show this message and exit.



		Usage: scheduler get [OPTIONS] REPORT_TYPE
		
		  Fetch report from ZooKeeper and return it as a DataFrame.
		
		Options:
		  --match TEXT
		  --help        Show this message and exit.



		Usage: server create [OPTIONS] RSRC_ID RSRC
		
		  Create server.
		
		Options:
		  --help  Show this message and exit.

		Usage: server delete [OPTIONS] RSRC_ID
		
		  Delete server.
		
		Options:
		  --help  Show this message and exit.

		Usage: server get [OPTIONS] RSRC_ID
		
		  Get server configuration.
		
		Options:
		  --help  Show this message and exit.

		Usage: server list [OPTIONS]
		
		  List servers by cell and/or features.
		
		Options:
		  --partition TEXT
		  --cell TEXT
		  --help            Show this message and exit.

		Usage: server update [OPTIONS] RSRC_ID RSRC
		
		  Update server.
		
		Options:
		  --help  Show this message and exit.



		Usage: tenant create [OPTIONS] RSRC_ID RSRC
		
		  Create tenant.
		
		Options:
		  --help  Show this message and exit.

		Usage: tenant delete [OPTIONS] RSRC_ID
		
		  Delete tenant.
		
		Options:
		  --help  Show this message and exit.

		Usage: tenant get [OPTIONS] RSRC_ID
		
		  Get tenant configuration.
		
		Options:
		  --help  Show this message and exit.

		Usage: tenant list [OPTIONS]
		
		  List tenants.
		
		Options:
		  --help  Show this message and exit.

		Usage: tenant update [OPTIONS] RSRC_ID RSRC
		
		  Update tenant.
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.ldap
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: ldap_group [OPTIONS] COMMAND [ARGS]...
		
		  Manage Treadmill LDAP data
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  allocation  Manage allocations
		  app         Manage applications
		  app-group   Manage App Groups
		  cell        Manage cell configuration
		  direct      Direct access to LDAP data
		  dns         Manage Critical DNS server configuration
		  haproxy     Manage HAProxies
		  init        Initializes the LDAP directory structure
		  partition   Manage partitions
		  schema      View or update LDAP schema
		  server      Manage server configuration
		  tenant      Manage tenants



		Usage: ldap_group allocation [OPTIONS] COMMAND [ARGS]...
		
		  Manage allocations
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  assign     Manage application assignments
		  configure  Create, get or modify allocation...
		  delete     Delete an allocation
		  list       List configured allocations
		  reserve    Reserve capacity on a given cell

		Usage: ldap_group app [OPTIONS] COMMAND [ARGS]...
		
		  Manage applications
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  configure  Create, get or modify an app configuration
		  delete     Delete applicaiton
		  list       List configured applicaitons

		Usage: ldap_group app-group [OPTIONS] COMMAND [ARGS]...
		
		  Manage App Groups
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  cells      Add or remove cells from the app-group
		  configure  Create, get or modify an App Group
		  delete     Delete an App Group entry
		  get        Get an App Group entry
		  list       List App Group entries

		Usage: ldap_group cell [OPTIONS] COMMAND [ARGS]...
		
		  Manage cell configuration
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  configure  Create, get or modify cell configuration
		  delete     Delete a cell
		  insert     Add master server to a cell
		  list       Displays master servers
		  remove     Remove master server from a cell

		Usage: ldap_group direct [OPTIONS] COMMAND [ARGS]...
		
		  Direct access to LDAP data
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  delete  Delete LDAP object by DN
		  get     List all defined DNs
		  list    List all defined DNs

		Usage: ldap_group dns [OPTIONS] COMMAND [ARGS]...
		
		  Manage Critical DNS server configuration
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  configure  Create, get or modify Critical DNS quorum
		  delete     Delete Critical DNS server
		  list       Displays Critical DNS servers list

		Usage: ldap_group haproxy [OPTIONS] COMMAND [ARGS]...
		
		  Manage HAProxies
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  configure  Create, get or modify HAProxy servers
		  delete     Delete a partition
		  list       List partitions

		Usage: ldap_group init [OPTIONS]
		
		  Initializes the LDAP directory structure
		
		Options:
		  --help  Show this message and exit.

		Usage: ldap_group partition [OPTIONS] COMMAND [ARGS]...
		
		  Manage partitions
		
		Options:
		  --cell TEXT  [required]
		  --help       Show this message and exit.
		
		Commands:
		  configure  Create, get or modify partition configuration
		  delete     Delete a partition
		  list       List partitions

		Usage: ldap_group schema [OPTIONS]
		
		  View or update LDAP schema
		
		Options:
		  -u, --update  Refresh LDAP schema.
		  --help        Show this message and exit.

		Usage: ldap_group server [OPTIONS] COMMAND [ARGS]...
		
		  Manage server configuration
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  configure  Create, get or modify server configuration
		  delete     Delete server(s)
		  list       List servers

		Usage: ldap_group tenant [OPTIONS] COMMAND [ARGS]...
		
		  Manage tenants
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  configure  Create, get or modify tenant configuration
		  delete     Delete a tenant
		  list       List configured tenants



		Usage: allocation assign [OPTIONS] ALLOCATION
		
		  Manage application assignments
		
		Options:
		  --pattern TEXT      Application name pattern.  [required]
		  --priority INTEGER  Assigned priority.  [required]
		  --cell TEXT         Cell.  [required]
		  --delete            Delete assignment.
		  --help              Show this message and exit.

		Usage: allocation configure [OPTIONS] ALLOCATION
		
		  Create, get or modify allocation configuration
		
		Options:
		  -e, --environment [dev|qa|uat|prod]
		                                  Environment
		  --help                          Show this message and exit.

		Usage: allocation delete [OPTIONS] ALLOCATION
		
		  Delete an allocation
		
		Options:
		  --help  Show this message and exit.

		Usage: allocation list [OPTIONS]
		
		  List configured allocations
		
		Options:
		  --help  Show this message and exit.

		Usage: allocation reserve [OPTIONS] ALLOCATION
		
		  Reserve capacity on a given cell
		
		Options:
		  -m, --memory TEXT              Memory.
		  -c, --cpu TEXT                 CPU.
		  -d, --disk TEXT                Disk.
		  -r, --rank INTEGER             Rank.
		  -a, --rank-adjustment INTEGER  Rank adjustment.
		  -u, --max-utilization FLOAT    Max utilization.
		  -t, --traits LIST              Allocation traits
		  -p, --partition TEXT           Allocation partition
		  --cell TEXT                    Cell.  [required]
		  --help                         Show this message and exit.



		Usage: app configure [OPTIONS] APP
		
		  Create, get or modify an app configuration
		
		Options:
		  -m, --manifest PATH  Application manifest.
		  --help               Show this message and exit.

		Usage: app delete [OPTIONS] APP
		
		  Delete applicaiton
		
		Options:
		  --help  Show this message and exit.

		Usage: app list [OPTIONS]
		
		  List configured applicaitons
		
		Options:
		  --help  Show this message and exit.



		Usage: app-group cells [OPTIONS] NAME
		
		  Add or remove cells from the app-group
		
		Options:
		  --add LIST     Cells to to add.
		  --remove LIST  Cells to to remove.
		  --help         Show this message and exit.

		Usage: app-group configure [OPTIONS] NAME
		
		  Create, get or modify an App Group
		
		Options:
		  --group-type TEXT  App group type
		  --cell LIST        Cell app pattern could be in; comma separated list of cells
		  --pattern TEXT     App pattern
		  --endpoints LIST   App group endpoints, comma separated list.
		  --data LIST        App group specific data as key=value comma separated list
		  --help             Show this message and exit.

		Usage: app-group delete [OPTIONS] NAME
		
		  Delete an App Group entry
		
		Options:
		  --help  Show this message and exit.

		Usage: app-group get [OPTIONS] NAME
		
		  Get an App Group entry
		
		Options:
		  --help  Show this message and exit.

		Usage: app-group list [OPTIONS]
		
		  List App Group entries
		
		Options:
		  --help  Show this message and exit.



		Usage: cell configure [OPTIONS] CELL
		
		  Create, get or modify cell configuration
		
		Options:
		  -v, --version TEXT       Version.
		  -r, --root TEXT          Distro root.
		  -l, --location TEXT      Cell location.
		  -u, --username TEXT      Cell proid account.
		  --archive-server TEXT    Archive server.
		  --archive-username TEXT  Archive username.
		  --ssq-namespace TEXT     SSQ namespace.
		  -d, --data PATH          Cell specific data in YAML
		  --status TEXT            Cell status
		  -m, --manifest PATH      Load cell from manifest file.
		  --help                   Show this message and exit.

		Usage: cell delete [OPTIONS] CELL
		
		  Delete a cell
		
		Options:
		  --help  Show this message and exit.

		Usage: cell insert [OPTIONS] CELL
		
		  Add master server to a cell
		
		Options:
		  --idx [1|2|3|4|5]            Master index.  [required]
		  --hostname TEXT              Master hostname.  [required]
		  --client-port INTEGER        Zookeeper client port.  [required]
		  --kafka-client-port INTEGER  Kafka client port.
		  --jmx-port INTEGER           Zookeeper jmx port.
		  --followers-port INTEGER     Zookeeper followers port.
		  --election-port INTEGER      Zookeeper election port.
		  --help                       Show this message and exit.

		Usage: cell list [OPTIONS]
		
		  Displays master servers
		
		Options:
		  --help  Show this message and exit.

		Usage: cell remove [OPTIONS] CELL
		
		  Remove master server from a cell
		
		Options:
		  --idx [1|2|3]  Master index.  [required]
		  --help         Show this message and exit.



		Usage: direct delete [OPTIONS] REC_DN
		
		  Delete LDAP object by DN
		
		Options:
		  --help  Show this message and exit.

		Usage: direct get [OPTIONS] REC_DN
		
		  List all defined DNs
		
		Options:
		  -c, --cls TEXT    Object class  [required]
		  -a, --attrs LIST  Addition attributes
		  --help            Show this message and exit.

		Usage: direct list [OPTIONS]
		
		  List all defined DNs
		
		Options:
		  --root TEXT  Search root.
		  --help       Show this message and exit.



		Usage: dns configure [OPTIONS] NAME
		
		  Create, get or modify Critical DNS quorum
		
		Options:
		  --server LIST        Server name
		  -m, --manifest PATH  Load DNS from manifest file
		  --help               Show this message and exit.

		Usage: dns delete [OPTIONS] NAME
		
		  Delete Critical DNS server
		
		Options:
		  --help  Show this message and exit.

		Usage: dns list [OPTIONS] [NAME]
		
		  Displays Critical DNS servers list
		
		Options:
		  --server TEXT  List servers matching this name
		  --help         Show this message and exit.



		Usage: haproxy configure [OPTIONS] HAPROXY
		
		  Create, get or modify HAProxy servers
		
		Options:
		  -c, --cell TEXT  Treadmll cell
		  --help           Show this message and exit.

		Usage: haproxy delete [OPTIONS] HAPROXY
		
		  Delete a partition
		
		Options:
		  --help  Show this message and exit.

		Usage: haproxy list [OPTIONS]
		
		  List partitions
		
		Options:
		  --help  Show this message and exit.



		Usage: partition configure [OPTIONS] PARTITION
		
		  Create, get or modify partition configuration
		
		Options:
		  -m, --memory TEXT          Memory.
		  -c, --cpu TEXT             CPU.
		  -d, --disk TEXT            Disk.
		  -s, --systems LIST         System eon id list
		  -t, --down-threshold TEXT  Down threshold.
		  --help                     Show this message and exit.

		Usage: partition delete [OPTIONS] LABEL
		
		  Delete a partition
		
		Options:
		  --help  Show this message and exit.

		Usage: partition list [OPTIONS]
		
		  List partitions
		
		Options:
		  --help  Show this message and exit.



		Usage: server configure [OPTIONS] SERVER
		
		  Create, get or modify server configuration
		
		Options:
		  -c, --cell TEXT       Treadmll cell
		  -t, --traits TEXT     List of server traits
		  -p, --partition TEXT  Server partition
		  -d, --data PATH       Server specific data in JSON
		  --help                Show this message and exit.

		Usage: server delete [OPTIONS] [SERVERS]...
		
		  Delete server(s)
		
		Options:
		  --help  Show this message and exit.

		Usage: server list [OPTIONS]
		
		  List servers
		
		Options:
		  -c, --cell TEXT       Treadmll cell.
		  -t, --traits TEXT     List of server traits
		  -p, --partition TEXT  Server partition
		  --help                Show this message and exit.



		Usage: tenant configure [OPTIONS] TENANT
		
		  Create, get or modify tenant configuration
		
		Options:
		  -s, --system INTEGER  System eon id
		  --help                Show this message and exit.

		Usage: tenant delete [OPTIONS] TENANT
		
		  Delete a tenant
		
		Options:
		  --help  Show this message and exit.

		Usage: tenant list [OPTIONS]
		
		  List configured tenants
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.logs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: logs [OPTIONS] APP_OR_SVC
		
		  View application's service logs.
		
		Options:
		  --cell TEXT     [required]
		  --host TEXT     Hostname where to look for the logs  [required]
		  --uniq TEXT     The container uniq id
		  --service TEXT  The name of the service for which the logs are to be retreived
		  --help          Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.master
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: master_group [OPTIONS] COMMAND [ARGS]...
		
		  Manage Treadmill master data
		
		Options:
		  --cell TEXT       [required]
		  --zookeeper TEXT
		  --help            Show this message and exit.
		
		Commands:
		  app             Manage app configuration
		  bucket          Manage Treadmill bucket configuration
		  cell            Manage top level cell configuration
		  identity-group  Manage identity group configuration
		  monitor         Manage app monitors configuration
		  server          Manage server configuration



		Usage: master_group app [OPTIONS] COMMAND [ARGS]...
		
		  Manage app configuration
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  configure  View app instance configuration
		  delete     Deletes (unschedules) the app by pattern
		  list       List apps
		  schedule   Schedule app(s) on the cell master

		Usage: master_group bucket [OPTIONS] COMMAND [ARGS]...
		
		  Manage Treadmill bucket configuration
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  configure  Create, get or modify bucket configuration
		  delete     Delete bucket
		  list       Delete bucket

		Usage: master_group cell [OPTIONS] COMMAND [ARGS]...
		
		  Manage top level cell configuration
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  insert  Add top level bucket to the cell
		  list    List top level bucket in the cell
		  remove  Remove top level bucket to the cell

		Usage: master_group identity-group [OPTIONS] COMMAND [ARGS]...
		
		  Manage identity group configuration
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  configure  Create, get or modify identity group...
		  delete     Deletes identity group
		  list       List all configured identity groups

		Usage: master_group monitor [OPTIONS] COMMAND [ARGS]...
		
		  Manage app monitors configuration
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  configure  Create, get or modify an app monitor...
		  delete     Deletes app monitor
		  list       List all configured monitors

		Usage: master_group server [OPTIONS] COMMAND [ARGS]...
		
		  Manage server configuration
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  configure  Create, get or modify server configuration
		  delete     Delete server configuration
		  list       List servers



		Usage: app configure [OPTIONS] INSTANCE
		
		  View app instance configuration
		
		Options:
		  --help  Show this message and exit.

		Usage: app delete [OPTIONS] [APPS]...
		
		  Deletes (unschedules) the app by pattern
		
		Options:
		  --help  Show this message and exit.

		Usage: app list [OPTIONS]
		
		  List apps
		
		Options:
		  --help  Show this message and exit.

		Usage: app schedule [OPTIONS] APP
		
		  Schedule app(s) on the cell master
		
		Options:
		  -m, --manifest PATH      [required]
		  --env [dev|qa|uat|prod]  Proid environment.  [required]
		  --proid TEXT             Proid.  [required]
		  -n, --count INTEGER
		  --help                   Show this message and exit.



		Usage: bucket configure [OPTIONS] BUCKET
		
		  Create, get or modify bucket configuration
		
		Options:
		  -f, --features TEXT  Bucket features, - to reset
		  --help               Show this message and exit.

		Usage: bucket delete [OPTIONS] BUCKET
		
		  Delete bucket
		
		Options:
		  --help  Show this message and exit.

		Usage: bucket list [OPTIONS]
		
		  Delete bucket
		
		Options:
		  --help  Show this message and exit.



		Usage: cell insert [OPTIONS] BUCKET
		
		  Add top level bucket to the cell
		
		Options:
		  --help  Show this message and exit.

		Usage: cell list [OPTIONS]
		
		  List top level bucket in the cell
		
		Options:
		  --help  Show this message and exit.

		Usage: cell remove [OPTIONS] BUCKET
		
		  Remove top level bucket to the cell
		
		Options:
		  --help  Show this message and exit.



		Usage: identity-group configure [OPTIONS] GROUP
		
		  Create, get or modify identity group configuration
		
		Options:
		  -n, --count INTEGER
		  --help               Show this message and exit.

		Usage: identity-group delete [OPTIONS] GROUP
		
		  Deletes identity group
		
		Options:
		  --help  Show this message and exit.

		Usage: identity-group list [OPTIONS]
		
		  List all configured identity groups
		
		Options:
		  --help  Show this message and exit.



		Usage: monitor configure [OPTIONS] APP
		
		  Create, get or modify an app monitor configuration
		
		Options:
		  -n, --count INTEGER
		  --help               Show this message and exit.

		Usage: monitor delete [OPTIONS] APP
		
		  Deletes app monitor
		
		Options:
		  --help  Show this message and exit.

		Usage: monitor list [OPTIONS]
		
		  List all configured monitors
		
		Options:
		  --help  Show this message and exit.



		Usage: server configure [OPTIONS] SERVER
		
		  Create, get or modify server configuration
		
		Options:
		  -f, --features TEXT  Server features, - to reset.
		  -p, --parent TEXT    Server parent / separated.
		  -m, --memory TEXT    Server memory.
		  -c, --cpu TEXT       Server cpu, %.
		  -d, --disk TEXT      Server disk.
		  --help               Show this message and exit.

		Usage: server delete [OPTIONS] SERVER
		
		  Delete server configuration
		
		Options:
		  --help  Show this message and exit.

		Usage: server list [OPTIONS]
		
		  List servers
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.node
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: node_group [OPTIONS] COMMAND [ARGS]...
		
		  Manage Treadmill node data
		
		Options:
		  --aliases-path TEXT  Colon separated command alias paths
		  --help               Show this message and exit.
		
		Commands:
		  benchmark  Benchmark node IO performance
		  lvm        Set up LVM on node



		Usage: node_group benchmark [OPTIONS]
		
		  Benchmark node IO performance
		
		Options:
		  --benchmark-publish-file PATH  File for benchmark process to publish result
		                                 [required]
		  --vg-name TEXT                 Benchmark this volume group
		  --underlying-device-name PATH  Underlying device name of the vg
		  --underlying-image-path PATH   Underlying image path of the vg
		  --benchmark-volume TEXT        Benchmark file size, fio size
		  --rw-type TEXT                 Benchmark r/w type, fio rw
		  --job-number TEXT              Benchmark process number, fio numjobs
		  --thread-number TEXT           Benchmark thread number each process, fio
		                                 iodepth
		  --iops-block-size TEXT         small block size to find max iops, fio bs
		  --bps-block-size TEXT          large block size to find max bps, fio bs
		  --max-seconds TEXT             Benchmark max run time in seconds, fio runtime
		  --help                         Show this message and exit.

		Usage: node_group lvm [OPTIONS] COMMAND [ARGS]...
		
		  Set up LVM on node
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  device  Set up LVM on device
		  image   Set up LVM on image file



		Usage: lvm device [OPTIONS]
		
		  Set up LVM on device
		
		Options:
		  --device-name PATH  Set up LVM this device  [required]
		  --help              Show this message and exit.

		Usage: lvm image [OPTIONS]
		
		  Set up LVM on image file
		
		Options:
		  --image-path PATH  Set up LVM on an image file under this path  [required]
		  --image-size TEXT  Image file size  [required]
		  --image-name TEXT  Image file name
		  --help             Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.ok
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: ok [OPTIONS]
		
		  Check status of Zookeeper ensemble.
		
		Options:
		  --cell TEXT  [required]
		  --help       Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.postmortem
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: collect [OPTIONS]
		
		  Collect Treadmill node data
		
		Options:
		  --treadmill-root PATH  Treadmill root path.  [required]
		  --upload-user TEXT     Upload postmortem statistics with this user.
		                         [required]
		  --upload-url TEXT      Upload postmortem statistics to this file url.
		  --help                 Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.scheduler
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: top [OPTIONS] COMMAND [ARGS]...
		
		  Report scheduler state.
		
		Options:
		  --zookeeper TEXT
		  --cell TEXT       [required]
		  --help            Show this message and exit.
		
		Commands:
		  explain  Explain scheduler internals
		  view     Examine scheduler state.



		Usage: top explain [OPTIONS] COMMAND [ARGS]...
		
		  Explain scheduler internals
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  placement  Explain application placement
		  queue      Explain the application queue

		Usage: top view [OPTIONS] COMMAND [ARGS]...
		
		  Examine scheduler state.
		
		Options:
		  --reschedule
		  --help        Show this message and exit.
		
		Commands:
		  allocs   View allocation report
		  apps     View apps report
		  queue    View utilization queue
		  reboots  View server reboot times.
		  servers  View servers report



		Usage: explain placement [OPTIONS] INSTANCE
		
		  Explain application placement
		
		Options:
		  --mode [full|default|servers]  Tree traversal method
		  --help                         Show this message and exit.

		Usage: explain queue [OPTIONS]
		
		  Explain the application queue
		
		Options:
		  --instance TEXT   Application instance
		  --partition TEXT  Cell partition
		  --help            Show this message and exit.



		Usage: view allocs [OPTIONS]
		
		  View allocation report
		
		Options:
		  --help  Show this message and exit.

		Usage: view apps [OPTIONS]
		
		  View apps report
		
		Options:
		  --help  Show this message and exit.

		Usage: view queue [OPTIONS]
		
		  View utilization queue
		
		Options:
		  --help  Show this message and exit.

		Usage: view reboots [OPTIONS]
		
		  View server reboot times.
		
		Options:
		  --histogram  Print histogram of reboot times
		  --help       Show this message and exit.

		Usage: view servers [OPTIONS]
		
		  View servers report
		
		Options:
		  --features / --no-features
		  --help                      Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.show
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: top [OPTIONS] COMMAND [ARGS]...
		
		  Show Treadmill apps
		
		Options:
		  --cell TEXT       [required]
		  --zookeeper TEXT
		  --help            Show this message and exit.
		
		Commands:
		  pending    List pending applications
		  running    List running applications
		  scheduled  List scheduled applications
		  stopped    List stopped applications



		Usage: top pending [OPTIONS]
		
		  List pending applications
		
		Options:
		  --help  Show this message and exit.

		Usage: top running [OPTIONS]
		
		  List running applications
		
		Options:
		  --help  Show this message and exit.

		Usage: top scheduled [OPTIONS]
		
		  List scheduled applications
		
		Options:
		  --help  Show this message and exit.

		Usage: top stopped [OPTIONS]
		
		  List stopped applications
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.ssh
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: ssh [OPTIONS] APP [COMMAND]...
		
		  SSH into Treadmill container.
		
		Options:
		  --cell TEXT  [required]
		  --ssh PATH   SSH client to use.
		  --help       Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.trace
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: trace [OPTIONS] APP
		
		  Trace application events.
		
		  Invoking treadmill_trace with non existing application instance will cause
		  the utility to wait for the specified instance to be started.
		
		  Specifying already finished instance of the application will display
		  historical trace information and exit status.
		
		Options:
		  --last
		  --snapshot
		  --cell TEXT  [required]
		  --help       Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.wait
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: wait [OPTIONS] [INSTANCES]...
		
		  Wait for all instances to exit.
		
		Options:
		  --cell TEXT  [required]
		  --help       Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.allocation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: allocation [OPTIONS] COMMAND [ARGS]...
		
		  Manage Treadmill allocations.
		
		  Allocation is a group of applications that share same capacity. Each
		  allocation is partitioned by environment and cell. Given allocation, cell
		  and environment, users reserve capacity for their apps.
		
		  Allocations form a hierarchy, so that when reservation is underused, extra
		  capacity is offered to sibling apps first (by environment), and then up the
		  tree for applications in parent allocations.
		
		Options:
		  --api TEXT  API url to use.
		  --help      Show this message and exit.
		
		Commands:
		  assign     Assign application pattern:priority to the...
		  configure  Configure allocation.
		  delete     Delete a tenant/allocation/reservation.
		  list       List allocations.
		  reserve    Reserve capacity on the cell for given...



		Usage: allocation assign [OPTIONS] ALLOCATION
		
		  Assign application pattern:priority to the allocation.
		
		  Application pattern must start with <PROID>. and is a glob expression.
		
		  Environments of the proid and one specified in command line using --env
		  option must match.
		
		  Once scheduled, Treadmill scheduler will match application against all
		  available patterns and assign application to a reserved capacity.
		
		  All application assigned to a capacity are ordered by priority from high to
		  low.
		
		Options:
		  -e, --env TEXT      Environment.  [required]
		  -c, --cell TEXT     Treadmill cell  [required]
		  --pattern TEXT      Application pattern.  [required]
		  --priority INTEGER  Assignment priority.
		  --delete            Delete assignment.
		  --help              Show this message and exit.

		Usage: allocation configure [OPTIONS] ALLOCATION
		
		  Configure allocation.
		
		  Allocation name is global, and is associated with list of systems.
		
		Options:
		  -s, --systems LIST  System ID
		  --help              Show this message and exit.

		Usage: allocation delete [OPTIONS] ITEM
		
		  Delete a tenant/allocation/reservation.
		
		Options:
		  --help  Show this message and exit.

		Usage: allocation list [OPTIONS]
		
		  List allocations.
		
		Options:
		  --help  Show this message and exit.

		Usage: allocation reserve [OPTIONS] ALLOCATION
		
		  Reserve capacity on the cell for given environment.
		
		Options:
		  -e, --env TEXT             Environment.  [required]
		  -c, --cell TEXT            Treadmill cell  [required]
		  -p, --partition TEXT       Allocation partition
		  -r, --rank INTEGER         Allocation rank
		  --rank-adjustment INTEGER  Rank adjustment
		  --max-utilization FLOAT    Maximum utilization
		  --empty                    Make empty (zero capacity) reservation.
		  --memory G|M               Memory demand.
		  --cpu XX%                  CPU demand, %.
		  --disk G|M                 Disk demand.
		  --help                     Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.build_binary
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: build-binary [OPTIONS]
		
		  Build treadmill binary and RPM
		
		Options:
		  -s, --source TEXT           Treadmill source directory path  [required]
		  -t, --release-tag TEXT      Release tag
		  -m, --release-message TEXT  Release message
		  --help                      Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.cell
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: cell [OPTIONS] COMMAND [ARGS]...
		
		  List & display Treadmill cells.
		
		Options:
		  --api TEXT  API url to use.
		  --help      Show this message and exit.
		
		Commands:
		  configure  Display the details of a cell.
		  list       List the configured cells.



		Usage: cell configure [OPTIONS] NAME
		
		  Display the details of a cell.
		
		Options:
		  --help  Show this message and exit.

		Usage: cell list [OPTIONS]
		
		  List the configured cells.
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.cloud
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: cloud [OPTIONS] COMMAND [ARGS]...
		
		  Manage Treadmill on cloud
		
		Options:
		  --domain TEXT  Domain for hosted zone  [required]
		  --api TEXT     API URL  [required]
		  --help         Show this message and exit.
		
		Commands:
		  configure  Configure Treadmill EC2 Objects
		  delete     Delete Treadmill EC2 Objects
		  ipa        Create & Delete IPA Users, Hosts and Services
		  list       Show Treadmill Cloud Resources



		Usage: cloud configure [OPTIONS] COMMAND [ARGS]...
		
		  Configure Treadmill EC2 Objects
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  cell  Configure Treadmill Cell
		  ldap  Configure Treadmill LDAP
		  node  Configure new Node in Cell

		Usage: cloud delete [OPTIONS] COMMAND [ARGS]...
		
		  Delete Treadmill EC2 Objects
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  cell  Delete Cell
		  ldap  Delete LDAP
		  node  Delete Node

		Usage: cloud ipa [OPTIONS] COMMAND [ARGS]...
		
		  Create & Delete IPA Users, Hosts and Services
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  host     Create and Delete IPA Hosts
		  service  Add and Delete IPA Service
		  user     Create and Delete IPA Users

		Usage: cloud list [OPTIONS] COMMAND [ARGS]...
		
		  Show Treadmill Cloud Resources
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  cell  Show Cell(s)
		  vpc   Show VPC(s)



		Usage: configure cell [OPTIONS]
		
		  Configure Treadmill Cell
		
		Options:
		  --vpc-name TEXT            VPC Name  [required]
		  --region TEXT              Region for the vpc
		  --name TEXT                Treadmill master name  [default: TreadmillMaster]
		  --key TEXT                 SSH Key Name  [required]
		  --image TEXT               Image to use for new instances e.g. RHEL-7.4
		                             [required]
		  --subnet-name TEXT         Cell(Subnet) Name  [required]
		  --instance-type TEXT       AWS ec2 instance type  [default: t2.micro]
		  --tm-release TEXT          Treadmill release to use
		  --app-root TEXT            Treadmill app root  [default: /var/tmp]
		  --cidr-block TEXT          CIDR block for the cell  [default: 172.23.0.0/24]
		  --ipa-admin-password TEXT  Password for IPA admin
		  -m, --manifest TEXT        Options YAML file.  NOTE: This argument is mutually
		                             exclusive with arguments: [ipa_admin_password,
		                             region, instance_type, vpc_name,
		                             cidr_blocksubnet_name, key, name, app_root,
		                             tm_release, image].
		  --help                     Show this message and exit.

		Usage: configure ldap [OPTIONS]
		
		  Configure Treadmill LDAP
		
		Options:
		  --vpc-name TEXT            VPC name  [required]
		  --key TEXT                 SSH Key Name  [required]
		  --name TEXT                LDAP Instance Name  [required]
		  --image TEXT               Image to use for instances e.g. RHEL-7.4
		                             [required]
		  --subnet-name TEXT         Subnet Name for LDAP  [required]
		  --region TEXT              Region for the vpc
		  --instance-type TEXT       AWS ec2 instance type  [default: t2.micro]
		  --tm-release TEXT          Treadmill release to use
		  --app-root TEXT            Treadmill app root  [default: /var/tmp]
		  --ldap-cidr-block TEXT     CIDR block for LDAP  [default: 172.23.1.0/24]
		  --ipa-admin-password TEXT  Password for IPA admin
		  -m, --manifest TEXT        Options YAML file.  NOTE: This argument is mutually
		                             exclusive with arguments: [region,
		                             ipa_admin_passwordldap_cidr_block, instance_type,
		                             vpc_name, key, name, subnet_name, app_root,
		                             tm_release, image].
		  --help                     Show this message and exit.

		Usage: configure node [OPTIONS]
		
		  Configure new Node in Cell
		
		Options:
		  --vpc-name TEXT            VPC Name  [required]
		  --region TEXT              Region for the vpc
		  --name TEXT                Node name  [default: TreadmillNode]
		  --key TEXT                 SSH Key Name  [required]
		  --image TEXT               Image to use for new node instance e.g. RHEL-7.4
		                             [required]
		  --subnet-name TEXT         Cell(Subnet) Name  [required]
		  --instance-type TEXT       AWS ec2 instance type  [default: t2.large]
		  --tm-release TEXT          Treadmill release to use
		  --app-root TEXT            Treadmill app root  [default: /var/tmp/treadmill-
		                             node]
		  --ipa-admin-password TEXT  Password for IPA admin
		  --with-api                 Provision node with Treadmill APIs  [default:
		                             False]
		  -m, --manifest TEXT        Options YAML file.  NOTE: This argument is mutually
		                             exclusive with arguments: [ipa_admin_password,
		                             region, instance_type, vpc_name, key, name,
		                             subnet_name, app_root, tm_release, image,
		                             with_api].
		  --help                     Show this message and exit.



		Usage: delete cell [OPTIONS]
		
		  Delete Cell
		
		Options:
		  --vpc-name TEXT     VPC Name  [required]
		  --subnet-name TEXT  Cell(Subnet) Name  [required]
		  --help              Show this message and exit.

		Usage: delete ldap [OPTIONS]
		
		  Delete LDAP
		
		Options:
		  --vpc-name TEXT  VPC Name  [required]
		  --name TEXT      LDAP Name  [default: TreadmillLDAP; required]
		  --help           Show this message and exit.

		Usage: delete node [OPTIONS]
		
		  Delete Node
		
		Options:
		  --vpc-name TEXT  VPC Name  [required]
		  --name TEXT      Node Name  [required]
		  --help           Show this message and exit.



		Usage: ipa host [OPTIONS] COMMAND [ARGS]...
		
		  Create and Delete IPA Hosts
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Creates an IPA Host
		  delete  Deletes an IPA Host

		Usage: ipa service [OPTIONS] COMMAND [ARGS]...
		
		  Add and Delete IPA Service
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  add  Adds an IPA Service

		Usage: ipa user [OPTIONS] COMMAND [ARGS]...
		
		  Create and Delete IPA Users
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Creates an IPA User
		  delete  Deletes an IPA User



		Usage: host create [OPTIONS] HOSTNAME
		
		  Creates an IPA Host
		
		Options:
		  --help  Show this message and exit.

		Usage: host delete [OPTIONS] HOSTNAME
		
		  Deletes an IPA Host
		
		Options:
		  --help  Show this message and exit.



		Usage: service add [OPTIONS] HOSTNAME SERVICE
		
		  Adds an IPA Service
		
		Options:
		  --help  Show this message and exit.



		Usage: user create [OPTIONS] USERNAME
		
		  Creates an IPA User
		
		Options:
		  --help  Show this message and exit.

		Usage: user delete [OPTIONS] USERNAME
		
		  Deletes an IPA User
		
		Options:
		  --help  Show this message and exit.



		Usage: list cell [OPTIONS]
		
		  Show Cell(s)
		
		Options:
		  --vpc-name TEXT   VPC Name  [required]
		  --cell-name TEXT  Cell(Subnet) Name
		  --help            Show this message and exit.

		Usage: list vpc [OPTIONS]
		
		  Show VPC(s)
		
		Options:
		  --vpc-name TEXT  VPC Name
		  --help           Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.configure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: configure [OPTIONS] [APPNAME]
		
		  Configure a Treadmill app
		
		Options:
		  --api TEXT           API url to use.
		  -m, --manifest PATH  App manifest file (stream)
		  --delete             Delete the app.
		  --help               Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.cron
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: cron_group [OPTIONS] COMMAND [ARGS]...
		
		  Manage Treadmill cron jobs
		
		Options:
		  --api URL    API url to use.
		  --cell TEXT  [required]
		  --help       Show this message and exit.
		
		Commands:
		  configure  Create or modify an existing app start...
		  delete     Delete a cron events
		  list       List out all cron events
		  pause      Pause a cron job
		  resume     Resume a cron job



		Usage: cron_group configure [OPTIONS] JOB_ID [EVENT]
		
		  Create or modify an existing app start schedule
		
		Options:
		  --resource TEXT    The resource to schedule, e.g. an app name
		  --expression TEXT  The cron expression for scheduling
		  --count INTEGER    The number of instances to start
		  --help             Show this message and exit.

		Usage: cron_group delete [OPTIONS] JOB_ID
		
		  Delete a cron events
		
		Options:
		  --help  Show this message and exit.

		Usage: cron_group list [OPTIONS]
		
		  List out all cron events
		
		Options:
		  --match TEXT     Cron name pattern match
		  --resource TEXT  Pattern match on the resource name
		  --help           Show this message and exit.

		Usage: cron_group pause [OPTIONS] JOB_ID
		
		  Pause a cron job
		
		Options:
		  --help  Show this message and exit.

		Usage: cron_group resume [OPTIONS] JOB_ID
		
		  Resume a cron job
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.discovery
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: discovery [OPTIONS] APP [ENDPOINT]
		
		  Show state of scheduled applications.
		
		Options:
		  --cell TEXT       [required]
		  --wsapi URL       Websocket API.
		  --check-state
		  --watch
		  --separator TEXT
		  --help            Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.identity_group
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: monitor_group [OPTIONS] COMMAND [ARGS]...
		
		  Manage identity group configuration
		
		Options:
		  --cell TEXT  [required]
		  --api URL    API url to use.
		  --help       Show this message and exit.
		
		Commands:
		  configure  Configure application monitor
		  delete     Delete identity group
		  list       List configured identity groups



		Usage: monitor_group configure [OPTIONS] NAME
		
		  Configure application monitor
		
		Options:
		  -n, --count INTEGER  Identity count
		  --help               Show this message and exit.

		Usage: monitor_group delete [OPTIONS] NAME
		
		  Delete identity group
		
		Options:
		  --help  Show this message and exit.

		Usage: monitor_group list [OPTIONS]
		
		  List configured identity groups
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.krb
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: run [OPTIONS] COMMAND [ARGS]...
		
		  Manage Kerberos tickets.
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.logs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: logs [OPTIONS] APP_OR_SVC
		
		  View application's service logs.
		
		  Arguments are expected to be specified a) either as one string or b) parts
		  defined one-by-one ie.:
		
		  a) <appname>/<uniq or running>/service/<servicename>
		
		  b) <appname> --uniq <uniq> --service <servicename>
		
		  Eg.:
		
		  a) proid.foo#1234/xz9474as8/service/my-echo
		
		  b) proid.foo#1234 --uniq xz9474as8 --service my-echo
		
		  For the latest log simply omit 'uniq':
		
		  proid.foo#1234 --service my-echo
		
		Options:
		  --api URL       State API url to use.
		  --cell TEXT     [required]
		  --host TEXT     Hostname where to look for the logs
		  --service TEXT  The name of the service for which the logs are to be retreived
		  --uniq TEXT     The container id. Specify this if you look for a not-running
		                  (terminated) application's log
		  --ws-api URL    Websocket API url to use.
		  --help          Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.manage
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: manage [OPTIONS] COMMAND [ARGS]...
		
		  Manage applications.
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.monitor
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: monitor_group [OPTIONS] COMMAND [ARGS]...
		
		  Manage Treadmill app monitor configuration
		
		Options:
		  --cell TEXT  [required]
		  --api URL    API url to use.
		  --help       Show this message and exit.
		
		Commands:
		  configure  Configure application monitor
		  delete     Delete app monitor
		  list       List configured app monitors



		Usage: monitor_group configure [OPTIONS] NAME
		
		  Configure application monitor
		
		Options:
		  -n, --count INTEGER  Instance count
		  --help               Show this message and exit.

		Usage: monitor_group delete [OPTIONS] NAME
		
		  Delete app monitor
		
		Options:
		  --help  Show this message and exit.

		Usage: monitor_group list [OPTIONS]
		
		  List configured app monitors
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.render
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: interpolate [OPTIONS] INPUTFILE [PARAMS]...
		
		  Interpolate input file template.
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.run
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: run [OPTIONS] APPNAME [COMMAND]...
		
		  Schedule Treadmill app.
		
		  With no options, will schedule already configured app, fail if app is not
		  configured.
		
		  When manifest (or other options) are specified, they will be merged on top
		  of existing manifest if it exists.
		
		Options:
		  --cell TEXT                   [required]
		  --api URL                     API url to use.
		  --count INTEGER               Number of instances to start
		  -m, --manifest PATH           App manifest file (stream)
		  --memory G|M                  Memory demand, default 100M.
		  --cpu XX%                     CPU demand, default 10%.
		  --disk G|M                    Disk demand, default 100M.
		  --tickets LIST                Tickets.
		  --service TEXT                Service name.
		  --restart-limit INTEGER       Service restart limit.
		  --restart-interval INTEGER    Service restart limit interval.
		  --endpoint <TEXT INTEGER>...  Network endpoint.
		  --help                        Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.scheduler
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: run [OPTIONS] COMMAND [ARGS]...
		
		  Report scheduler state.
		
		Options:
		  --cell TEXT  Treadmill cell  [required]
		  --api URL    Cell API URL
		  --help       Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.scheduler.allocs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: allocs [OPTIONS]
		
		  View allocations report.
		
		Options:
		  --match TEXT  Server name pattern match
		  --help        Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.scheduler.apps
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: apps [OPTIONS]
		
		  View apps report.
		
		Options:
		  --match TEXT  Server name pattern match
		  --full
		  --help        Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.scheduler.servers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: servers [OPTIONS]
		
		  View servers report.
		
		Options:
		  --match TEXT  Server name pattern match
		  --help        Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.server
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: server [OPTIONS] COMMAND [ARGS]...
		
		  List & display Treadmill servers.
		
		Options:
		  --api TEXT  API url to use.
		  --help      Show this message and exit.
		
		Commands:
		  configure  Display details of the server.
		  list       List all servers.



		Usage: server configure [OPTIONS] NAME
		
		  Display details of the server.
		
		Options:
		  --help  Show this message and exit.

		Usage: server list [OPTIONS]
		
		  List all servers.
		
		Options:
		  --cell TEXT       Filter servers by cell  [required]
		  --partition TEXT  Filter servers by partition
		  --help            Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.show
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: show [OPTIONS] COMMAND [ARGS]...
		
		  Show state of scheduled applications.
		
		Options:
		  --cell TEXT  [required]
		  --api URL    API url to use.
		  --help       Show this message and exit.
		
		Commands:
		  all        Show scheduled instances.
		  endpoints  Show application endpoints.
		  finished   Show finished instances.
		  instance   Show scheduled instance manifest.
		  pending    Show pending instances.
		  running    Show running instances.
		  scheduled  Show scheduled instances.
		  state      Show state of Treadmill scheduled instances.



		Usage: show all [OPTIONS]
		
		  Show scheduled instances.
		
		Options:
		  --match TEXT      Application name pattern match
		  --partition TEXT  Filter apps by partition
		  --help            Show this message and exit.

		Usage: show endpoints [OPTIONS] PATTERN [ENDPOINT] [PROTO]
		
		  Show application endpoints.
		
		Options:
		  --help  Show this message and exit.

		Usage: show finished [OPTIONS]
		
		  Show finished instances.
		
		Options:
		  --match TEXT      Application name pattern match
		  --partition TEXT  Filter apps by partition
		  --help            Show this message and exit.

		Usage: show instance [OPTIONS] INSTANCE_ID
		
		  Show scheduled instance manifest.
		
		Options:
		  --help  Show this message and exit.

		Usage: show pending [OPTIONS]
		
		  Show pending instances.
		
		Options:
		  --match TEXT      Application name pattern match
		  --partition TEXT  Filter apps by partition
		  --help            Show this message and exit.

		Usage: show running [OPTIONS]
		
		  Show running instances.
		
		Options:
		  --match TEXT      Application name pattern match
		  --partition TEXT  Filter apps by partition
		  --help            Show this message and exit.

		Usage: show scheduled [OPTIONS]
		
		  Show scheduled instances.
		
		Options:
		  --match TEXT      Application name pattern match
		  --partition TEXT  Filter apps by partition
		  --help            Show this message and exit.

		Usage: show state [OPTIONS]
		
		  Show state of Treadmill scheduled instances.
		
		Options:
		  --match TEXT  Application name pattern match
		  --finished    Show finished instances.
		  --help        Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.sproc
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: run [OPTIONS] COMMAND [ARGS]...
		
		  Run system processes
		
		Options:
		  --cgroup TEXT     Create separate cgroup for the service.
		  --cell TEXT       [required]
		  --zookeeper TEXT
		  --help            Show this message and exit.
		
		Commands:
		  ad               Manage Active Directory integration.
		  appcfgmgr        Starts appcfgmgr process.
		  appevents        Publish application events.
		  appmonitor       Sync LDAP data with Zookeeper data.
		  cellsync         Sync LDAP data with Zookeeper data.
		  cgroup           Manage core cgroups.
		  cgroup-server    Create pge server to provide authorize...
		  checkout         Test treadmill infrastructure.
		  cleanup          Start cleanup process.
		  configure        Configure local manifest and schedule app to...
		  cron             Run Treadmill master scheduler.
		  eventdaemon      Listens to Zookeeper events.
		  exec             Exec command line in treadmill environment.
		  export-reports   Export scheduler reports from ZooKeeper to...
		  finish           Finish treadmill application on the node.
		  firewall         Manage Treadmill firewall.
		  haproxy          Run Treadmill HAProxy
		  host-aliases     Manage /etc/hosts aliases.
		  host-ring        Manage /etc/hosts file inside the container.
		  init             Run treadmill init process.
		  kafka            Run Treadmill Kafka
		  keytabs          Manage Kerberos keytabs.
		  metrics          Collect node and container metrics.
		  monitor          Monitor group of services.
		  nodeinfo         Runs nodeinfo server.
		  presence         Register container/app presence.
		  reboot-monitor   Runs node reboot monitor.
		  restapi          Run Treadmill API server.
		  scheduler        Run Treadmill master scheduler.
		  service          Run local node service.
		  tickets          Manage Kerberos tickets.
		  trace            Manage Treadmill traces.
		  version-monitor  Monitor group of services.
		  vring            Run vring manager.
		  websocket        Treadmill Websocket
		  zk2fs            Starts appcfgmgr process.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.ssh
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: ssh [OPTIONS] APP [COMMAND]...
		
		  SSH into Treadmill container.
		
		Options:
		  --wsapi URL  WS API url to use.
		  --api URL    API url to use.
		  --cell TEXT  [required]
		  --wait       Wait until the app starts up
		  --ssh PATH   SSH client to use.
		  --help       Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.stop
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: stop [OPTIONS] [INSTANCES]...
		
		  Stop (unschedule, terminate) Treadmill instance(s).
		
		Options:
		  --cell TEXT  [required]
		  --api URL    API url to use.
		  --all        Stop all instances matching the app provided
		  --help       Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.supervise
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: run [OPTIONS] COMMAND [ARGS]...
		
		  Cross-cell supervision tools.
		
		Options:
		  --help  Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.supervise.multi_cell_monitor
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: controller [OPTIONS] NAME
		
		  Control app monitors across cells
		
		Options:
		  --cell TEXT                  [required]
		  --monitor <TEXT INTEGER>...  [required]
		  --once                       Run once.
		  --interval TEXT              Wait interval between checks.
		  --help                       Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.supervise.reaper
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: reaper [OPTIONS] PATTERN ENDPOINT [COMMAND]...
		
		  Removes unhealthy instances of the app.
		
		  The health check script reads from STDIN and prints to STDOUT.
		
		  The input it list of instance host:port, similar to discovery.
		
		  Output - list of instances that did not pass health check.
		
		  For example, specifying awk '{print $1}' as COMMAND will remove all
		  instances.
		
		Options:
		  --cell TEXT          [required]
		  --once               Run once.
		  --interval TEXT      Wait interval between checks.
		  --threshold INTEGER  Number of failed checks before reap.
		  --proto [tcp|udp]    Endpoint protocol.
		  --help               Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.trace
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: trace [OPTIONS] APP
		
		  Trace application events.
		
		  Invoking treadmill_trace with non existing application instance will cause
		  the utility to wait for the specified instance to be started.
		
		  Specifying already finished instance of the application will display
		  historical trace information and exit status.
		
		  Specifying only an application name will list all the instance IDs with
		  trace information available.
		
		  The trace will exit with the exit code of the container service that caused
		  container finish (reached retry count).
		
		  Special error codes if service did not exit gracefully and it is not
		  possible to capture the return code:
		
		      101 - container was aborted.     102 - container was killed (possible
		      out of memory)     100 - everything else.
		
		Options:
		  --cell TEXT  [required]
		  --api URL    REST API url to use.
		  --wsapi URL  WebSocket API url to use.
		  --last
		  --snapshot
		  --help       Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.trace_identity
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: trace [OPTIONS] IDENTITY_GROUP
		
		  Trace identity group events.
		
		  Invoking treadmill_trace with non existing application instance will cause
		  the utility to wait for the specified instance to be started.
		
		  Specifying already finished instance of the application will display
		  historical trace information and exit status.
		
		  Specifying only an application name will list all the instance IDs with
		  trace information available.
		
		Options:
		  --cell TEXT  [required]
		  --api URL    REST API url to use.
		  --wsapi URL  WebSocket API url to use.
		  --snapshot
		  --help       Show this message and exit.

