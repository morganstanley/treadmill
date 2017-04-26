
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
		  --ldap TEXT
		  --help       Show this message and exit.
		
		Commands:
		  blackout    Manage server and app blackouts.
		  cell        Upgrade the supplied cell
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



^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.cell
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: upgrade [OPTIONS] CELL
		
		  Upgrade the supplied cell
		
		Options:
		  --ldap TEXT              [required]
		  --ldap-search-base TEXT  [required]
		  --batch INTEGER          Upgrade batch size.
		  --timeout INTEGER        Upgrade timeout.
		  --treadmill_root TEXT    Treadmill root dir.
		  --continue_on_error      Stop if batch upgrade failed.
		  --dry_run                Dry run, verify status.
		  --force                  Force event if server appears up-to-date
		  --servers TEXT           Servers to upgrade.
		  --help                   Show this message and exit.

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



		Usage: diag psmem [OPTIONS]
		
		  Reports memory utilization details for given container.
		
		Options:
		  --fast         Disale statm/pss analysis.
		  --cgroup TEXT  Cgroup to evaluate.
		  --help         Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.discovery
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: top [OPTIONS] APP [ENDPOINT]
		
		  Discover container endpoints.
		
		Options:
		  --cell TEXT       [required]
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



^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.install
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: install [OPTIONS] COMMAND [ARGS]...
		
		  Installs Treadmill.
		
		Options:
		  --cell TEXT        [required]
		  --zookeeper TEXT   [required]
		  --config FILENAME  [required]
		  --help             Show this message and exit.
		
		Commands:
		  master  Installs Treadmill master.
		  node    Installs Treadmill node.



^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.invoke
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: invoke [OPTIONS] COMMAND [ARGS]...
		
		  Directly invoke Treadmill API without REST.
		
		Options:
		  --auth / --no-auth
		  --cell TEXT         [required]
		  --help              Show this message and exit.
		
		Commands:
		  allocation      Treadmill Allocation REST api.
		  app             Treadmill App REST api.
		  app_group       Treadmill AppGroup REST api.
		  app_monitor     Treadmill AppMonitor REST api.
		  cell            Treadmill Cell REST api.
		  dns             Treadmill DNS REST api.
		  identity_group  Treadmill Identity Group REST api.
		  instance        Treadmill Instance REST api.
		  local           Treadmill Local REST api.
		  nodeinfo        Treadmill Local REST api.
		  server          Treadmill Server REST api.
		  tenant          Treadmill Tenant REST api.



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

		Usage: ldap_group init [OPTIONS] DOMAIN
		
		  Initializes the LDAP directory structure
		
		Options:
		  --help  Show this message and exit.

		Usage: ldap_group schema [OPTIONS]
		
		  View or update LDAP schema
		
		Options:
		  -l, --load FILENAME  Schema (YAML) file.
		  --help               Show this message and exit.

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
		
		Error: Missing option "--cell".



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



^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.show
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: top [OPTIONS] COMMAND [ARGS]...
		
		  Show Treadmill apps
		
		Options:
		  --cell TEXT  [required]
		  --help       Show this message and exit.
		
		Commands:
		  pending    List pending applications
		  running    List running applications
		  scheduled  List scheduled applications
		  stopped    List stopped applications



^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.admin.ssh
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: ssh [OPTIONS] APP [COMMAND]...
		
		  SSH into Treadmill container.
		
		Options:
		  --cell TEXT     [required]
		  --ssh FILENAME  SSH client to use.
		  --help          Show this message and exit.

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
		  list       Configure allocation tenant.
		  reserve    Reserve capacity on the cell.



		Usage: allocation assign [OPTIONS] ALLOCATION
		
		  Assign application pattern:priority to the allocation.
		
		Options:
		  -c, --cell TEXT     Treadmill cell  [required]
		  --pattern TEXT      Application pattern.
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

		Usage: allocation list [OPTIONS]
		
		  Configure allocation tenant.
		
		Options:
		  --help  Show this message and exit.

		Usage: allocation reserve [OPTIONS] ALLOCATION
		
		  Reserve capacity on the cell.
		
		Options:
		  -c, --cell TEXT     Treadmill cell
		  -l, --label TEXT    Allocation label
		  -r, --rank INTEGER  Allocation rank
		  --memory G|M        Memory demand.
		  --cpu XX%           CPU demand, %.
		  --disk G|M          Disk demand.
		  --help              Show this message and exit.

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



		Usage: aws cell [OPTIONS]
		
		  Manage treadmill cell on AWS
		
		Options:
		  --create           Create a new treadmill cell on AWS
		  --destroy          Destroy treadmill cell on AWS
		  --playbook TEXT    Playbok file
		  --inventory TEXT   Inventory file
		  --key-file TEXT    AWS ssh pem file
		  --aws-config TEXT  AWS config file
		  --help             Show this message and exit.

		Usage: aws init [OPTIONS]
		
		  Initialise ansible files for AWS deployment
		
		Options:
		  --help  Show this message and exit.

		Usage: aws node [OPTIONS]
		
		  Manage treadmill node
		
		Options:
		  --create           Create a new treadmill node
		  --playbook TEXT    Playbok file
		  --inventory TEXT   Inventory file
		  --key-file TEXT    AWS ssh pem file
		  --aws-config TEXT  AWS config file
		  --help             Show this message and exit.

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
Module: treadmill.cli.configure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: configure [OPTIONS] [APPNAME]
		
		  Configure a Treadmill app
		
		Options:
		  --api TEXT               API url to use.
		  -m, --manifest FILENAME  App manifest file (stream)
		  --delete                 Delete the app.
		  --help                   Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.discovery
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: discovery [OPTIONS] APP [ENDPOINT]
		
		  Show state of scheduled applications.
		
		Options:
		  --cell TEXT       [required]
		  --api URL         API url to use.
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

		Usage: logs [OPTIONS] SERVICE
		
		  View application logs.
		
		Options:
		  --cell TEXT  [required]
		  --api URL    API url to use.
		  --host TEXT  hostname.
		  --help       Show this message and exit.

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

		Usage: metrics [OPTIONS] [APP]
		
		  Retrieve node / app metrics.
		
		Options:
		  --cell TEXT        [required]
		  -o, --outdir PATH  Output directory.  [required]
		  --servers LIST     List of servers to get core metrics
		  --services LIST    Subset of core services.
		  --help             Show this message and exit.

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



^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.pid1
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: pid1 [OPTIONS]
		
		  Install dependencies
		
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
		  -m, --manifest FILENAME       App manifest file (stream)
		  --memory G|M                  Memory demand.
		  --cpu XX%                     CPU demand, %.
		  --disk G|M                    Disk demand.
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
		  instance   Show scheduled instance manifest.
		  pending    Show pending instances.
		  running    Show running instances.
		  scheduled  Show scheduled instances.
		  state      Show state of Treadmill scheduled instances.



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
		  cleanup          Start cleanup process.
		  configure        Configure local manifest and schedule app to...
		  eventdaemon      Listens to Zookeeper events.
		  exec             Exec command line in treadmill environment.
		  finish           Finish treadmill application on the node.
		  firewall         Manage Treadmill firewall.
		  init             Run treadmill init process.
		  kafka            Run Treadmill Kafka
		  metrics          Collect node and container metrics.
		  nodeinfo         Runs nodeinfo server.
		  presence         Register container/app presence.
		  reboot-monitor   Runs node reboot monitor.
		  restapi          Run Treadmill API server.
		  run              Runs container given a container dir.
		  scheduler        Run Treadmill master scheduler.
		  service          Run local node service.
		  task             Manage Treadmill tasks.
		  tickets          Manage Kerberos tickets.
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
		  --api URL       API url to use.
		  --cell TEXT     [required]
		  --ssh FILENAME  SSH client to use.
		  --help          Show this message and exit.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Module: treadmill.cli.stop
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
::

		Usage: stop [OPTIONS] [INSTANCES]...
		
		  Stop (unschedule, terminate) Treadmill instance(s).
		
		Options:
		  --cell TEXT  [required]
		  --api URL    API url to use.
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

