# 摩根项目进展情况

## Phase 1

Start scheduler process in master, and start the necessary services in server. It can schedule and run apps but has some problems when the app should be cleanup.

[Code History](https://github.com/gaocegege/treadmill/commits/dev/SJTU)

### Before Mar 7

Read related papers and code.

### Mar 7

Try to run treadmill, use ApacheDS as LDAP server, but the code in public repo could not work.

### Mar 13

Try to run scheduler process in master separately. Remove LDAP.

### Mar 17

Use `./bin/treadmill --debug admin master server configure` and `./bin/treadmill --debug admin master app schedule` to allocate server and app.

### Mar 20

Import vagrant, and use bash script to start network service, cgroup service and local disk service in server side. Init server with `./bin/treadmill sproc init`, instead.

### Mar 22

Hack eventmanager

### Apr 6

Hack App Config Manager

### Apr 12

Hack supervisor

### Apr 22

Add set up script to set up the environment in vagrant VM. And do some hacks to run server without errors

### Apr 24

Fix some bugs in local-up bash script, and run rrdcached in server side.

### May 4

Add bash script to export environment variables.

## Phase 2

Try to use vagrant maintained by TW, but it doesn't work well. Start to write benchmarks and simulator for treadmill scheduler, and use R Language Notebook to present the result.

[Code History](https://github.com/gaocegege/treadmill/commits/dev/2017-5-18)
[Tech Report(Work in Progress)](http://gaocegege.com/treadmill/)

### May 19

Implement the first benchmark.

### June 1

Record the result of the benchmark, and profile scheduler. Show the result in R Language Notebook.

### June 15

Add two benchmarks.

## Phase 3(July 19)

Simulate the logic of treadmill scheduler and Kubernetes scheduler, compare the result and select the solution.

## Phase 4(July 30)

Implement the logic of the final solution for scheduler.

## Future Work

1. Support node monitor to schduler the applications.
2. Support affinity, anti-affinity, taint and other advanced features.
3. Support scheduler extender to support customization.
4. Support concurrent and semi-distributed schedulers. 
