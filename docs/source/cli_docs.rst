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
		  --zookeeper TEXT
		  --help            Show this message and exit.
		
		Commands:
		  blackout    Manage server and app blackouts.
		  checkout    Run interactive checkout.
		  cron        Manage Treadmill cron jobs
		  diag        Local node and container diagnostics.
		  discovery   Discover container endpoints.
		  http        Invoke Treadmill HTTP REST API.
		  install     Installs Treadmill.
		  invoke      Directly invoke Treadmill API without REST.
		  ldap        Manage Treadmill LDAP data
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



		DNS domain is not set.

		
		
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
		  --help            Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.install.openldap
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: openldap [OPTIONS]
		
		  Installs Treadmill Openldap server.
		
		Options:
		  --gssapi            use gssapi auth.
		  -p, --rootpw TEXT   password hash, generated by slappass -s <pwd>.
		  -o, --owner TEXT    root user.
		  -s, --suffix TEXT   suffix (e.g dc=example,dc=com).  [required]
		  -u, --uri TEXT      uri, e.g: ldap://...:20389  [required]
		  -m, --masters LIST  list of masters.
		  --run / --no-run
		  --help              Show this message and exit.

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
		  api_lookup      Treadmill API lookup API.
		  app             Treadmill App REST api.
		  app_group       Treadmill AppGroup REST api.
		  app_monitor     Treadmill AppMonitor REST api.
		  cell            Treadmill Cell REST api.
		  cloud_host      Treadmill Cloud Host REST API.
		  cron            Treadmill Cron REST api.
		  dns             Treadmill DNS REST api.
		  identity_group  Treadmill Identity Group REST api.
		  instance        Treadmill Instance REST api.
		  local           Treadmill Local REST api.
		  nodeinfo        Treadmill Local REST api.
		  server          Treadmill Server REST api.
		  tenant          Treadmill Tenant REST api.



		Usage: invoke allocation [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Allocation REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  assignment   Assignment API.
		  create       Create allocation.
		  delete       Delete allocation.
		  get          Get allocation configuration.
		  list         List allocations.
		  reservation  Reservation API.
		  update       Update allocation.

		Usage: invoke api_lookup [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill API lookup API.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  adminapi  Treadmill Admin API Lookup API
		  cellapi   Treadmill Cell API Lookup API
		  get       No get method
		  list      Constructs a command handler.
		  stateapi  Treadmill State API Lookup API
		  wsapi     Treadmill WS API Lookup API

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

		Usage: invoke app_group [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill AppGroup REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Create (configure) application.
		  delete  Delete configured application.
		  get     Get application configuration.
		  list    List configured applications.
		  update  Update application configuration.

		Usage: invoke app_monitor [OPTIONS] COMMAND [ARGS]...
		
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

		Usage: invoke cloud_host [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Cloud Host REST API.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create  Constructs a command handler.
		  delete  Constructs a command handler.

		Usage: invoke cron [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Cron REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  create     Create (configure) instance.
		  delete     Delete configured instance.
		  get        Get instance configuration.
		  list       List configured instances.
		  scheduler  Lazily get scheduler
		  update     Update instance configuration.

		Usage: invoke dns [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill DNS REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  get   Get DNS server entry
		  list  List DNS servers

		Usage: invoke identity_group [OPTIONS] COMMAND [ARGS]...
		
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

		Usage: invoke local [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Local REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  archive  Access to archive files.
		  get      Get instance info.
		  list     List all instances on the node.
		  log      Access to log files.
		  metrics  Acess to the locally gathered metrics.

		Usage: invoke nodeinfo [OPTIONS] COMMAND [ARGS]...
		
		  Treadmill Local REST api.
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  get  Get hostname nodeinfo endpoint info.

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

		Usage: collect [OPTIONS] COMMAND [ARGS]...
		
		  Collect Treadmill node data
		
		Options:
		  --install-dir TEXT    Treadmill node install directory.
		  --upload_script TEXT  upload script to upload post-mortem file
		  --upload_args TEXT    arguments for upload script
		  --help                Show this message and exit.



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
		  view  Examine scheduler state.



		Usage: top view [OPTIONS] COMMAND [ARGS]...
		
		  Examine scheduler state.
		
		Options:
		  --reschedule
		  --help        Show this message and exit.
		
		Commands:
		  allocs   View allocation report
		  apps     View apps report
		  queue    View utilization queue
		  servers  View servers report

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
		
		  Configure Treadmill allocations.
		
		Options:
		  --api TEXT  API url to use.
		  --help      Show this message and exit.
		
		Commands:
		  assign     Assign application pattern:priority to the...
		  configure  Configure allocation tenant.
		  delete     Delete a tenant/allocation/reservation.
		  list       Configure allocation tenant.
		  reserve    Reserve capacity on the cell.



		Usage: allocation assign [OPTIONS] ALLOCATION
		
		  Assign application pattern:priority to the allocation.
		
		Options:
		  -c, --cell TEXT     Treadmill cell  [required]
		  --pattern TEXT      Application pattern.  [required]
		  --priority INTEGER  Assignment priority.
		  --delete            Delete assignment.
		  --help              Show this message and exit.

		Usage: allocation configure [OPTIONS] TENANT
		
		  Configure allocation tenant.
		
		Options:
		  -s, --systems LIST  System ID
		  -e, --env TEXT      Environment
		  -n, --name TEXT     Allocation name
		  --help              Show this message and exit.

		Usage: allocation delete [OPTIONS] ITEM
		
		  Delete a tenant/allocation/reservation.
		
		Options:
		  --help  Show this message and exit.

		Usage: allocation list [OPTIONS]
		
		  Configure allocation tenant.
		
		Options:
		  --help  Show this message and exit.

		Usage: allocation reserve [OPTIONS] ALLOCATION
		
		  Reserve capacity on the cell.
		
		Options:
		  -c, --cell TEXT       Treadmill cell
		  -p, --partition TEXT  Allocation partition
		  -r, --rank INTEGER    Allocation rank
		  --memory G|M          Memory demand.
		  --cpu XX%             CPU demand, %.
		  --disk G|M            Disk demand.
		  --help                Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.aws
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: aws [OPTIONS] COMMAND [ARGS]...
		
		  Manage treadmill on AWS
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  cell  Manage treadmill cell on AWS
		  init  Initialise ansible files for AWS deployment
		  node  Manage treadmill node



		
		Usage: aws init [OPTIONS]
		
		  Initialise ansible files for AWS deployment
		
		Options:
		  --help  Show this message and exit.

		
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
		  get   Display the details of a cell.
		  list  List the configured cells.



		Usage: cell get [OPTIONS] NAME
		
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
		
		  Manage treadmill on cloud
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  add-node            Add new node
		  delete              Delete Treadmill EC2 Objects
		  delete-hosted-zone  Delete Hosted Zones
		  disable-port        Disable Port from my ip
		  enable-port         Enable Port from my ip
		  init                Initialize treadmill VPC
		  init-cell           Initialize treadmill cell
		  init-domain         Initialize treadmill domain
		  init-ldap           Initialize treadmill cell
		  list                Show Treadmill Cloud Resources



		Usage: cloud add-node [OPTIONS]
		
		  Add new node
		
		Options:
		  --vpc-id TEXT              VPC ID of cell  [required]
		  --region TEXT              Region for the vpc
		  --domain TEXT              Domain for hosted zone  [required]
		  --name TEXT                Node name
		  --key TEXT                 SSH Key Name  [required]
		  --count INTEGER            Number of treadmill nodes to spin up
		  --image-id TEXT            AMI ID to use for new node instance  [required]
		  --instance-type TEXT       AWS ec2 instance type
		  --tm-release TEXT          Treadmill release to use
		  --ldap-hostname TEXT       LDAP hostname
		  --app-root TEXT            Treadmill app root
		  --subnet-id TEXT           Subnet ID  [required]
		  --ipa-admin-password TEXT  Password for IPA admin
		  --with-api                 Provision node with treadmill APIs
		  -m, --manifest TEXT        Options YAML file.  NOTE: This argument is mutually
		                             exclusive with arguments: [tm_release,
		                             ipa_admin_passwordwith_api, domain, ldap_hostname,
		                             instance_type, region, key, image_id, subnet_id,
		                             vpc_id, count, app_root, name].
		  --help                     Show this message and exit.

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

		Usage: cloud delete-hosted-zone [OPTIONS]
		
		  Delete Hosted Zones
		
		Options:
		  --zones-to-retain TEXT  Hosted Zone IDs to retain  [required]
		  --help                  Show this message and exit.

		Usage: cloud disable-port [OPTIONS]
		
		  Disable Port from my ip
		
		Options:
		  --protocol TEXT               Protocol
		  -p, --port TEXT               Port  [required]
		  -s, --security-group-id TEXT  Security Group ID  [required]
		  --help                        Show this message and exit.

		Usage: cloud enable-port [OPTIONS]
		
		  Enable Port from my ip
		
		Options:
		  --protocol TEXT               Protocol
		  -p, --port TEXT               Port  [required]
		  -s, --security-group-id TEXT  Security Group ID  [required]
		  --help                        Show this message and exit.

		Usage: cloud init [OPTIONS]
		
		  Initialize treadmill VPC
		
		Options:
		  --domain TEXT          Domain for hosted zone  [required]
		  --region TEXT          Region for the vpc
		  --vpc-cidr-block TEXT  CIDR block for the vpc
		  --secgroup_name TEXT   Security group name
		  --secgroup_desc TEXT   Description for the security group
		  -m, --manifest TEXT    Options YAML file.  NOTE: This argument is mutually
		                         exclusive with arguments: [domain, vpc_cidr_block,
		                         region, secgroup_desc, secgroup_name].
		  --help                 Show this message and exit.

		Usage: cloud init-cell [OPTIONS]
		
		  Initialize treadmill cell
		
		Options:
		  --vpc-id TEXT              VPC ID of cell  [required]
		  --region TEXT              Region for the vpc
		  --domain TEXT              Domain for hosted zone  [required]
		  --name TEXT                Treadmill master name
		  --key TEXT                 SSH Key Name  [required]
		  --count INTEGER            Number of treadmill masters to spin up
		  --image-id TEXT            AMI ID to use for new instances  [required]
		  --instance-type TEXT       AWS ec2 instance type
		  --tm-release TEXT          Treadmill release to use
		  --ldap-hostname TEXT       LDAP hostname
		  --app-root TEXT            Treadmill app root
		  --cell-cidr-block TEXT     CIDR block for the cell
		  --ldap-cidr-block TEXT     CIDR block for LDAP
		  --subnet-id TEXT           Subnet ID
		  --ldap-subnet-id TEXT      Subnet ID for LDAP
		  --without-ldap             Flag for LDAP Server
		  --ipa-admin-password TEXT  Password for IPA admin
		  -m, --manifest TEXT        Options YAML file.  NOTE: This argument is mutually
		                             exclusive with arguments: [tm_release,
		                             without_ldap, domain, ldap_hostname, instance_type,
		                             region, key, image_id, subnet_id,
		                             ipa_admin_password, cell_cidr_blockldap_subnet_id,
		                             ldap_cidr_block, vpc_id, count, app_root, name].
		  --help                     Show this message and exit.

		Usage: cloud init-domain [OPTIONS]
		
		  Initialize treadmill domain
		
		Options:
		  --name TEXT                Name of the instance
		  --region TEXT              Region for the vpc
		  --vpc-id TEXT              VPC ID of cell  [required]
		  --domain TEXT              Domain for hosted zone  [required]
		  --subnet-cidr-block TEXT   Cidr block of subnet for IPA
		  --subnet-id TEXT           Subnet ID
		  --count INTEGER            Count of the instances
		  --ipa-admin-password TEXT  Password for IPA admin
		  --tm-release TEXT          Treadmill Release
		  --key TEXT                 SSH key name  [required]
		  --instance-type TEXT       Instance type
		  --image-id TEXT            AMI ID to use for new master instance  [required]
		  -m, --manifest TEXT        Options YAML file.  NOTE: This argument is mutually
		                             exclusive with arguments: [tm_release, domain,
		                             instance_type, region, key, image_id,
		                             ipa_admin_password, vpc_id, count,
		                             subnet_cidr_blocksubnet_id, name].
		  --help                     Show this message and exit.

		Usage: cloud init-ldap [OPTIONS]
		
		  Initialize treadmill cell
		
		Options:
		  --vpc-id TEXT              VPC ID of cell  [required]
		  --region TEXT              Region for the vpc
		  --domain TEXT              Domain for hosted zone  [required]
		  --key TEXT                 SSH Key Name  [required]
		  --count INTEGER            Number of treadmill ldap instances to spin up
		  --image-id TEXT            AMI ID to use for instances  [required]
		  --instance-type TEXT       AWS ec2 instance type
		  --tm-release TEXT          Treadmill release to use
		  --ldap-hostname TEXT       LDAP hostname
		  --app-root TEXT            Treadmill app root
		  --ldap-cidr-block TEXT     CIDR block for LDAP
		  --ldap-subnet-id TEXT      Subnet ID for LDAP
		  --cell-subnet-id TEXT      Subnet ID of Cell
		  --ipa-admin-password TEXT  Password for IPA admin
		  -m, --manifest TEXT        Options YAML file.  NOTE: This argument is mutually
		                             exclusive with arguments: [tm_release,
		                             ipa_admin_passwordldap_cidr_block, ldap_subnet_id,
		                             cell_subnet_id, domain, ldap_hostname,
		                             instance_type, region, key, image_id, vpc_id,
		                             count, app_root].
		  --help                     Show this message and exit.

		Usage: cloud list [OPTIONS] COMMAND [ARGS]...
		
		  Show Treadmill Cloud Resources
		
		Options:
		  --help  Show this message and exit.
		
		Commands:
		  cell  Show Cell
		  vpc   Show VPC

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



		Usage: cron_group configure [OPTIONS] JOB_ID EVENT
		
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
Module: treadmill.cli.metrics
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: metrics [OPTIONS] COMMAND [ARGS]...
		
		  Retrieve node / app metrics.
		
		Options:
		  --cell-api TEXT    Cell API url to use.
		  --api TEXT         State API url to use.
		  --cell TEXT        [required]
		  -o, --outdir PATH  Output directory.  [required]
		  --ws-api TEXT      Websocket API url to use.
		  --help             Show this message and exit.
		
		Commands:
		  app      Get the metrics of the application in params.
		  running  Get the metrics of running instances.
		  sys      Get the metrics of the server(s) in params.



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
		  --match TEXT  Application name pattern match
		  --help        Show this message and exit.

		Usage: show endpoints [OPTIONS] PATTERN [ENDPOINT] [PROTO]
		
		  Show application endpoints.
		
		Options:
		  --help  Show this message and exit.

		Usage: show finished [OPTIONS]
		
		  Show finished instances.
		
		Options:
		  --match TEXT  Application name pattern match
		  --help        Show this message and exit.

		Usage: show instance [OPTIONS] INSTANCE_ID
		
		  Show scheduled instance manifest.
		
		Options:
		  --help  Show this message and exit.

		Usage: show pending [OPTIONS]
		
		  Show pending instances.
		
		Options:
		  --match TEXT  Application name pattern match
		  --help        Show this message and exit.

		Usage: show running [OPTIONS]
		
		  Show running instances.
		
		Options:
		  --match TEXT  Application name pattern match
		  --help        Show this message and exit.

		Usage: show scheduled [OPTIONS]
		
		  Show scheduled instances.
		
		Options:
		  --match TEXT  Application name pattern match
		  --help        Show this message and exit.

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
		  appcfgmgr        Starts appcfgmgr process.
		  appevents        Publish application events.
		  appmonitor       Sync LDAP data with Zookeeper data.
		  cellsync         Sync LDAP data with Zookeeper data.
		  cgroup           Manage core cgroups.
		  checkout         Test treadmill infrastructure.
		  cleanup          Start cleanup process.
		  configure        Configure local manifest and schedule app to...
		  cron             Run Treadmill master scheduler.
		  eventdaemon      Listens to Zookeeper events.
		  exec             Exec command line in treadmill environment.
		  finish           Finish treadmill application on the node.
		  firewall         Manage Treadmill firewall.
		  haproxy          Run Treadmill HAProxy
		  host-aliases     Manage /etc/hosts aliases.
		  host-ring        Manage /etc/hosts file inside the container.
		  init             Run treadmill init process.
		  kafka            Run Treadmill Kafka
		  metrics          Collect node and container metrics.
		  monitor          Monitor group of services.
		  nodeinfo         Runs nodeinfo server.
		  presence         Register container/app presence.
		  reboot-monitor   Runs node reboot monitor.
		  restapi          Run Treadmill API server.
		  run              Runs container given a container dir.
		  scheduler        Run Treadmill master scheduler.
		  service          Run local node service.
		  spawn            Spawn group.
		  tickets          Manage Kerberos tickets.
		  trace            Manage Treadmill traces.
		  version-monitor  Runs node version monitor.
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
		
		Commands:
		  multi-cell-monitor  Control app monitors across cells
		  reaper              Removes unhealthy instances of the app.

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

