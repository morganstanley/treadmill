"""MS specific aliases."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os

_SPAWN_VER = '2017.12.06-1'
_SPAWN_PATH = '/ms/dist/cloud/PROJ/treadmill-spawn/{0}/bin'.format(_SPAWN_VER)
_SPAWN_DEBUG = False


def get_bin_name(name, is_debug):
    """Gets the bin name with debug symbols if using debug."""
    if not is_debug:
        return name

    return '{0}-g'.format(name)


_LINUX_ALIASES = {
    # Netfilter utilities
    'conntrack': '/ms/dist/linux/PROJ/netfilter/1.4.2-0/sbin/conntrack',
    'ipset': [
        '/usr/sbin/ipset',
        '/ms/dist/linux/PROJ/ipset/6.21/sbin/ipset'
    ],

    # djbdns cache.
    'dnscache': '/ms/dist/aurora/PROJ/djbdns/1.05/bin/dnscache',

    # JAVA_HOME
    'java_home': '/ms/dist/msjava/PROJ/oraclejdk/1.8.0_121',

    # Customer PAM stacks
    'pam_ms_afs': '/ms/dist/afs/PROJ/pam_ms_afs/3.1',
    'pam_ms_krb5': '/ms/dist/sec/PROJ/pam_ms_krb5/4.3.3',
    'pam_pge': '/ms/dist/pge/PROJ/pam_pge/1.1.2',
    'pam_treadmill': '/ms/dist/cloud/PROJ/treadmill-pam/1.0',

    # https://kafka.apache.org/
    'kafka_run_class': '/ms/dist/esm/PROJ/kafka/0.10.1.0/bin/'
                       'kafka-run-class.sh',
    'kafka_server_start': '/ms/dist/esm/PROJ/kafka/0.10.1.0/bin/'
                          'kafka-server-start.sh',
    # HAProxy
    'haproxy': '/ms/dist/cloud/PROJ/haproxy/1.7.3/sbin/haproxy',

    # Kerberos utilities
    'kinit': '/ms/dist/sec/PROJ/ksymlinks/incr/bin/kinit',
    'klist': '/ms/dist/sec/PROJ/ksymlinks/incr/bin/klist',
    'krb5_keytab': '/ms/dist/aurora/bin/krb5_keytab',
    'krun': '/ms/dist/aurora/bin/krun',
    'ticket': '/ms/dist/aurora/sbin/ticket',

    # AFS utils
    'fs': '/bin/fs',

    # GIT for LDAP backups
    'git': '/ms/dist/fsf/PROJ/git/2.9.5/bin/git',

    # MS reboot command
    # TODO: need better abstraction for reboot script. It is probably ok to
    #       call it "reboot" but may need to support command line options in
    #       exe file like aliases.
    'reboot': '/ms/dist/aurora/PROJ/astro/prod/bin/auto_reboot',

    # Kuula binary for Webinfra installs (Zookeeper)
    'kuula': '/ms/dist/webinfra/PROJ/kuula/3.x-prod/bin/kuula',

    # https://www.isc.org/downloads/bind/
    'named': '/ms/dist/aurora/PROJ/bind/9.10/sbin/named',

    # http://skarnet.org/software/s6/
    # The s6 release is included in the TAR bind mounts.
    # treadmill.ms.plugins.fs.afs:MinimalAFSFilesystemPlugin
    'backtick': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/backtick',
    'cd': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/cd',
    'elglob': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/elglob',
    'emptyenv': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/emptyenv',
    'execlineb': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/execlineb',
    'exit': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/exit',
    'fdmove': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/fdmove',
    'fio': '/ms/dist/storage/PROJ/fio/2.0.15/bin/fio',
    'foreground': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/foreground',
    'if': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/if',
    'ifelse': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/ifelse',
    'import': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/import',
    'importas': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/importas',
    'iozone': '/ms/dist/storage/PROJ/iozone/3.465/bin/iozone',
    'loopwhilex': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/loopwhilex',
    'modulecmd': '/ms/dist/aurora/bin/modulecmd',
    'pipeline': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/pipeline',
    'redirfd': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/redirfd',
    's6': '/ms/dist/cloud/PROJ/s6/2.6.0.0',
    's6_envdir': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/s6-envdir',
    's6_envuidgid': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/s6-envuidgid',
    's6_log': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/s6-log',
    's6_setuidgid': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/s6-setuidgid',
    's6_svc': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/s6-svc',
    's6_svok': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/s6-svok',
    's6_svscan': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/s6-svscan',
    's6_svscanctl': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/s6-svscanctl',
    's6_svwait': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/s6-svwait',
    'umask': '/ms/dist/cloud/PROJ/s6/2.6.0.0/bin/umask',

    # https://github.com/elastic/logstash-forwarder
    'logstash-forwarder': '/ms/dist/esm/PROJ/laas-log-agent/prod/'
                          'logstash-forwarder',
    'pid1_distro': '/ms/dist/cloud/PROJ/treadmill-pid1/2.3',
    'pid1': '/ms/dist/cloud/PROJ/treadmill-pid1/2.3/bin/pid1',
    # http://oss.oetiker.ch/rrdtool/
    'rrdcached': '/ms/dist/fsf/PROJ/rrdtool/1.5.6-0/bin/rrdcached',
    'rrdtool': '/ms/dist/fsf/PROJ/rrdtool/1.5.6-0/bin/rrdtool',

    # OpenLDAP distribution
    'openldap': '/ms/dist/fsf/PROJ/openldap/2.4.45-0',
    'slapadd': '/ms/dist/fsf/PROJ/openldap/2.4.45-0/exec/sbin/slapadd',
    'slapd': '/ms/dist/fsf/PROJ/openldap/2.4.45-0/exec/libexec/slapd',
    'ldapsearch': '/ms/dist/fsf/PROJ/openldap/2.4.45-0/exec/bin/ldapsearch',

    # MS sshd version
    # The sshd release is included in the TAR bind mounts.
    # treadmill.ms.plugins.fs.afs:MinimalAFSFilesystemPlugin
    'sshd': '/ms/dist/sec/PROJ/openssh/5.8p2-ms2/sbin/sshd',

    # Treadmill utilities.
    'kt_add': '/ms/dist/cloud/PROJ/treadmill-tktfwd/1.9/bin/kt-add',
    'kt_split': '/ms/dist/cloud/PROJ/treadmill-tktfwd/1.9/bin/kt-split',
    'tkt_recv': '/ms/dist/cloud/PROJ/treadmill-tktfwd/1.9/bin/tkt-recv',
    'tkt_recv_v2': '/ms/dist/cloud/PROJ/treadmill-tktfwd/1.9/bin/tkt-recv-v2',
    'tkt_send': '/ms/dist/cloud/PROJ/treadmill-tktfwd/1.9/bin/tkt-send',
    'tkt_send_v2': '/ms/dist/cloud/PROJ/treadmill-tktfwd/1.9/bin/tkt-send-v2',

    # Shared libraries.
    #
    # ld_preload libs use $LIB notation, and in the code should be resolved
    # with check=False.
    #
    # The treadmill_bind_preload.so release is included in the TAR bind mounts.
    # treadmill.ms.plugins.fs.afs:MinimalAFSFilesystemPlugin
    #
    'treadmill_bind_distro': '/ms/dist/cloud/PROJ/treadmill-bind/5.1.0',
    'treadmill_bind_preload.so': '/ms/dist/cloud/PROJ/treadmill-bind/5.1.0/'
                                 '$LIB/treadmill_bind_preload.so',

    # Treadmill spawn utilities.
    'treadmill_spawn_path': _SPAWN_PATH,
    'treadmill_spawn': os.path.join(
        _SPAWN_PATH, get_bin_name('treadmill-spawn', _SPAWN_DEBUG)
    ),
    'treadmill_spawn_finish': os.path.join(
        _SPAWN_PATH, get_bin_name('treadmill-spawn-finish', _SPAWN_DEBUG),
    ),
    'treadmill_spawn_run': os.path.join(
        _SPAWN_PATH, get_bin_name('treadmill-spawn-run', _SPAWN_DEBUG),
    ),

    'webauthd': '/ms/dist/webinfra/PROJ/webauthd/default/sbin/webauthd'
}

_WINSS_PATH = '\\\\ms\\dist\\cloud\\PROJ\\winss\\2017.10.27-1\\msvc140_64'

_WINDOWS_ALIASES = {
    'winss': _WINSS_PATH,
    'winss_log': os.path.join(_WINSS_PATH, 'bin', 'winss-log.exe'),
    'winss_svc': os.path.join(_WINSS_PATH, 'bin', 'winss-svc.exe'),
    'winss_svok': os.path.join(_WINSS_PATH, 'bin', 'winss-svok.exe'),
    'winss_svscan': os.path.join(_WINSS_PATH, 'bin', 'winss-svscan.exe'),
    'winss_svscanctl': os.path.join(_WINSS_PATH, 'bin', 'winss-svscanctl.exe'),
    'winss_svwait': os.path.join(_WINSS_PATH, 'bin', 'winss-svwait.exe'),
}


if os.name == 'nt':
    ALIASES = _WINDOWS_ALIASES
else:
    ALIASES = _LINUX_ALIASES
