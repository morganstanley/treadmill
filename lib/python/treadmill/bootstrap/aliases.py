"""Default aliases.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import functools
import os

from treadmill import subproc


def _s6(exe):
    """Resolve s6 exe."""
    s6_dir = subproc.resolve('s6')
    if not s6_dir:
        return None

    return os.path.join(s6_dir, 'bin', exe.replace('_', '-'))


_BIN = functools.partial(os.path.join, '/bin')
_SBIN = functools.partial(os.path.join, '/sbin')
_USR_BIN = functools.partial(os.path.join, '/usr/bin')
_USR_SBIN = functools.partial(os.path.join, '/usr/sbin')


_LINUX_ALIASES = {
    # Standard Linux distribution, expect to find these in standard locations,
    # so setting value to None.
    'awk': _BIN,
    'basename': _BIN,
    'bc': _USR_BIN,
    'blkid': _SBIN,
    'brctl': _USR_SBIN,
    'cat': _BIN,
    'cgclear': _SBIN,
    'chmod': _BIN,
    'chown': _BIN,
    'chroot': _USR_SBIN,
    'conntrack': _SBIN,
    'cp': _BIN,
    'cut': _BIN,
    'date': _BIN,
    'dirname': _USR_BIN,
    'dmesg': _BIN,
    'docker': _USR_BIN,
    'dockerd': _USR_BIN,
    'docker_runtime': '/usr/libexec/docker/docker-runc-current',
    'dumpe2fs': _SBIN,
    'echo': _BIN,
    'expr': _USR_BIN,
    'find': _USR_BIN,
    'grep': _BIN,
    'gzip': _BIN,
    'head': _USR_BIN,
    'hostname': _BIN,
    'ifconfig': _SBIN,
    'ionice': _USR_BIN,
    'ip': _SBIN,
    'ipset': _SBIN,
    'iptables': _SBIN,
    'iptables_restore': '/sbin/iptables-restore',
    'kill': _BIN,
    'last': _USR_BIN,
    'ln': _BIN,
    'logrotate': _USR_SBIN,
    'losetup': _SBIN,
    'ls': _BIN,
    'lssubsys': _BIN,
    'lvm': _SBIN,
    'mkdir': _BIN,
    'mke2fs': _SBIN,
    'mkfifo': _USR_BIN,
    'mknod': _BIN,
    'mktemp': _BIN,
    'modprobe': _SBIN,
    'mount': _BIN,
    'mv': _BIN,
    'named': _USR_SBIN,
    'printf': _USR_BIN,
    'ps': _BIN,
    'pvremove': _SBIN,
    'pvs': _SBIN,
    'pwd': _BIN,
    'readlink': _BIN,
    'rm': _BIN,
    'rmdir': _BIN,
    'route': _SBIN,
    'sed': _BIN,
    'sleep': _BIN,
    'sshd': _BIN,
    'stat': _USR_BIN,
    'sysctl': _SBIN,
    'tail': _USR_BIN,
    'tar': _BIN,
    'touch': _BIN,
    'true': _BIN,
    'tune2fs': _SBIN,
    'umount': _BIN,
    'unshare': _USR_BIN,
    'vgchange': _SBIN,
    'vgremove': _SBIN,
    'watchdog': _USR_SBIN,
    'wc': _USR_BIN,

    # https://github.com/axboe/fio
    'fio': None,

    # s6 root dir.
    's6': None,

    # s6 utilities
    'backtick': _s6,
    'cd': _s6,
    'define': _s6,
    'dnscache': _s6,
    'elglob': _s6,
    'emptyenv': _s6,
    'execlineb': _s6,
    'exit': _s6,
    'fdmove': _s6,
    'forbacktickx': _s6,
    'foreground': _s6,
    'forstdin': _s6,
    'heredoc': _s6,
    'if': _s6,
    'ifelse': _s6,
    'ifte': _s6,
    'importas': _s6,
    'loopwhilex': _s6,
    'openldap': _s6,
    'pipeline': _s6,
    'redirfd': _s6,
    's6_envdir': _s6,
    's6_envuidgid': _s6,
    's6_fghack': _s6,
    's6_ipcclient': _s6,
    's6_ipcserver': _s6,
    's6_ipcserver_access': _s6,
    's6_log': _s6,
    's6_setuidgid': _s6,
    's6_svc': _s6,
    's6_svok': _s6,
    's6_svscan': _s6,
    's6_svscanctl': _s6,
    's6_svwait': _s6,
    'withstdinas': _s6,
    'umask': _s6,

    # Treadmill-bind.
    'treadmill_bind_distro': None,
    'treadmill_bind_preload.so': None,

    # Treadmill spawn.
    # TODO: should be moved to treadmill spawn aliases.
    'treadmill_spawn_path': None,
    'treadmill_spawn': None,
    'treadmill_spawn_finish': None,
    'treadmill_spawn_run': None,

    # Treadmill PID1
    'pid1': None,

    # Kerberos tools, default to standard locations.
    'kinit': None,
    'klist': None,

    # Treadmill krb tools
    'kt_add': None,
    'kt_split': None,
    'tkt_recv': None,
    'tkt_send': None,

    # RRD tools.
    'rrdcached': None,
    'rrdtool': None,

    # Open LDAP binaries.
    # TODO: should be moved to OpenLDAP aliases.
    'slapadd': None,
    'slapd': None,

    # Why do we need these?
    'logstash-forwarder': None,
}

_WINDOWS_ALIASES = {
    'winss': None,
    'winss_log': None,
    'winss_svc': None,
    'winss_svok': None,
    'winss_svscan': None,
    'winss_svscanctl': None,
    'winss_svwait': None,
    'powershell': 'C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\'
                  'powershell.exe',
}

if os.name == 'nt':
    ALIASES = _WINDOWS_ALIASES
else:
    ALIASES = _LINUX_ALIASES
