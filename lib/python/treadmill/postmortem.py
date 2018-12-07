"""Collect Treadmill node information after a crash.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import glob
import logging
import os
import shutil
import socket
import subprocess
import tarfile
import time
import six

if os.name == 'posix':
    from treadmill import cgroups
    from treadmill import cgutils

from treadmill import fs
from treadmill import subproc


_LOGGER = logging.getLogger(__name__)

# TODO: should use aliases instead.
_IFCONFIG = 'ifconfig'
_SYSCTL = 'sysctl'
_DMESG = 'dmesg'
_TAIL = 'tail'
_LVM = 'lvm'
_VGDISPLAY = 'vgdisplay'
_LVDISPLAY = 'lvdisplay'

_MAX_ARCHIVES = 3


def _datetime_utcnow():
    """Wrapper for datetime.datetime.utcnow for testability."""
    return datetime.datetime.utcnow()


def run(treadmill_root, cgroup_prefix):
    """Run postmortem"""
    filetime = _datetime_utcnow().strftime('%Y%m%d_%H%M%SUTC')
    hostname = socket.gethostname()
    postmortem_dir = os.path.join(treadmill_root, 'postmortem')
    fs.mkdir_safe(postmortem_dir)

    postmortem_archive = os.path.join(
        postmortem_dir, '{0}-{1}.tar.gz'.format(hostname, filetime)
    )

    _LOGGER.info('Collection postmortem: %s', postmortem_archive)

    with tarfile.open(postmortem_archive, 'w:gz') as f:
        collect(treadmill_root, f, cgroup_prefix)

    if os.name == 'posix':
        os.chmod(postmortem_archive, 0o644)

    existing = glob.glob(os.path.join(postmortem_dir, '*'))
    # Remove all files except for last two.
    for filename in sorted(existing)[0:-_MAX_ARCHIVES]:
        _LOGGER.info('Removing old archive: %s', filename)
        fs.rm_safe(filename)


def _safe_copy(src, dest):
    """Copy file from src to dest if need, generate sub directory for dest.
    """
    parent = os.path.dirname(dest)
    fs.mkdir_safe(parent)

    try:
        shutil.copyfile(src, dest)
        _LOGGER.debug('file copied %s => %s', src, dest)
    except OSError:
        _LOGGER.warning('skip %s => %s', src, dest)


def collect(approot, archive, cgroup_prefix):
    """Collect node information in case of blackout.

    :param approot:
        treadmill root, usually /var/tmp/treadmill
    :type approot:
        ``str``
    :param archive:
        archive file object
    :type archive:
        ``TarFile``
    """
    _LOGGER.info('save node info in %s', archive)

    collect_services(approot, archive)
    collect_running_app(approot, archive)
    if os.name == 'posix':
        collect_sysctl(archive)
        collect_cgroup(archive, cgroup_prefix)
        collect_localdisk(archive)
        collect_network(archive)
        collect_message(archive)

    return True


def _add_glob(archive, pattern):
    """Add files matching glob pattern to archive."""
    for filename in glob.glob(pattern):
        _LOGGER.debug('add: %s', filename)
        try:
            archive.add(filename)
        except Exception:  # pylint: disable=W0703
            _LOGGER.exception('Unable to add file: %s', filename)


def _add_output(archive, command):
    """Add output of command to the archive."""
    tarinfo = tarfile.TarInfo(os.path.join('diag', '#'.join(command)))
    tarinfo.mtime = time.time()
    try:
        output = subproc.check_output(command).encode(encoding='utf8',
                                                      errors='replace')
        stream = six.BytesIO(output)
        tarinfo.size = len(output)
    except subprocess.CalledProcessError as exc:
        output = str(exc).encode(encoding='utf8', errors='replace')
        stream = six.BytesIO(output)
        tarinfo.size = len(output)

    stream.seek(0)
    archive.addfile(tarinfo, fileobj=stream)


def collect_services(approot, archive):
    """Get treadmill init services information in node."""
    _add_glob(archive,
              os.path.join(approot, 'init', '*', 'log', 'current'))
    _add_glob(archive,
              os.path.join(approot, 'network_svc', '*'))
    _add_glob(archive,
              os.path.join(approot, 'localdisk_svc', '*'))
    _add_glob(archive,
              os.path.join(approot, 'cgroup_svc', '*'))
    _add_glob(archive,
              os.path.join(approot, 'presence_svc', '*'))


def collect_running_app(approot, archive):
    """Get treadmill running application information in node."""
    _add_glob(
        archive,
        os.path.join(approot, 'running', '*', 'log', 'current')
    )
    _add_glob(
        archive,
        os.path.join(approot, 'running', '*', 'data', 'log', 'current')
    )
    _add_glob(
        archive,
        os.path.join(approot, 'running', '*', 'data', 'sys', '*', 'data',
                     'log', 'current')
    )


def collect_sysctl(archive):
    """Get host sysctl (related to kernel)."""
    _add_output(archive, [_SYSCTL, '-a'])


def collect_cgroup(archive, cgroup_prefix):
    """Get host treadmill cgroups inforamation."""
    core_group = cgutils.core_group_name(cgroup_prefix)
    _add_glob(
        archive,
        os.path.join(cgroups.CGROOT, '*', core_group, '*')
    )
    apps_group = cgutils.apps_group_name(cgroup_prefix)
    _add_glob(
        archive,
        os.path.join(cgroups.CGROOT, '*', apps_group, '*', '*')
    )


def collect_localdisk(archive):
    """Get host local disk information."""
    _add_output(archive, [_LVM, _VGDISPLAY, 'treadmill'])
    _add_output(archive, [_LVM, _LVDISPLAY, 'treadmill'])


def collect_network(archive):
    """Get host network information."""
    _add_output(archive, [_IFCONFIG])


def collect_message(archive):
    """Get messages on the host."""
    _add_output(archive, [_DMESG])
    _add_output(archive, [_TAIL, '-n', '100', '/var/log/messages'])
