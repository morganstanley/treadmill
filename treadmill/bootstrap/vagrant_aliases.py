"""Vagrant aliases."""

ALIASES = {
    'pid1': '/opt/treadmill-pid1/bin/pid1',
    'treadmill': '/opt/treadmill',
    'treadmill_bin': '/opt/treadmill/bin/treadmill',
    'profile': 'vagrant',

    # openldap
    'slapd': '/usr/sbin/slapd',
    'slapadd': '/usr/sbin/slapadd',

    'dnscache': None,

    'java_home': None,
    'kafka_run_class': None,
    'kafka_server_start': None,

    # Kerberos
    'kinit': None,
    'klist': None,

    'tkt-recv': None,
    'tkt-send': None,

    'logstash-forwarder': None,

    'treadmill_bind_preload.so': None,
    'treadmill_spawn': None,
    'treadmill_spawn_finish': None,
    'treadmill_spawn_run': None,

    # s6 - use full path for all utilities, do not interpolate.
    's6': '/opt/s6',
    'backtick': '/opt/s6/bin/backtick',
    'elglob': '/opt/s6/bin/elglob',
    'emptyenv': '/opt/s6/bin/emptyenv',
    'execlineb': '/opt/s6/bin/execlineb',
    'fdmove': '/opt/s6/bin/fdmove',
    'if': '/opt/s6/bin/if',
    'import': '/opt/s6/bin/import',
    'importas': '/opt/s6/bin/importas',
    'redirfd': '/opt/s6/bin/redirfd',
    's6_envdir': '/opt/s6/bin/s6-envdir',
    's6_envuidgid': '/opt/s6/bin/s6-envuidgid',
    's6_log': '/opt/s6/bin/s6-log',
    's6_setuidgid': '/opt/s6/bin/s6-setuidgid',
    's6_svc': '/opt/s6/bin/s6-svc',
    's6_svok': '/opt/s6/bin/s6-svok',
    's6_svscan': '/opt/s6/bin/s6-svscan',
    's6_svscanctl': '/opt/s6/bin/s6-svscanctl',
    's6_svwait': '/opt/s6/bin/s6-svwait',
    'umask': '/opt/s6/bin/umask',
}
