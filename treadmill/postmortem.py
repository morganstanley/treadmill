"""Collect Treadmill node information after a crash.
"""


import os

import glob
import logging
import shutil
import tempfile

from treadmill import fs
from treadmill import subproc

_LOGGER = logging.getLogger(__name__)

_IFCONFIG = 'ifconfig'
_SYSCTL = 'sysctl'
_DMESG = 'dmesg'
_TAIL = 'tail'


def _safe_copy(src, dest):
    """Copy file from src to dest if need, generate sub directory for dest"""
    parent = os.path.dirname(dest)

    if not os.path.exists(parent):
        os.makedirs(parent)

    try:
        shutil.copyfile(src, dest)
        _LOGGER.debug('file copied %s => %s', src, dest)
    except OSError:
        _LOGGER.exception('unable to copy %s => %s', src, dest)


def collect(approot, archive_filename):
    """Collect node information in case of blackout.

    :param approot:
        treadmill root, usually /var/tmp/treadmill
    :type approot:
        ``str``
    :param archive_filename:
        archive path file
    :type archive_filename:
        ``str``
    """
    destroot = tempfile.mkdtemp()

    _LOGGER.info('save node info in %s', destroot)

    collect_init_services(approot, destroot)
    collect_running_app(approot, destroot)
    collect_sysctl(destroot)
    collect_cgroup(approot, destroot)
    collect_localdisk(approot, destroot)
    collect_network(approot, destroot)
    collect_message(destroot)

    try:
        archive_filename = fs.tar(sources=destroot,
                                  target=archive_filename,
                                  compression='gzip').name
        _LOGGER.info('node info archive file: %s', archive_filename)
        shutil.rmtree(destroot)
        return archive_filename
    except:  # pylint: disable=W0702
        # if tar bar is not generated successfully, we keep destroot
        # we can find destroot path in log to check the files
        _LOGGER.exception('Failed to generate node info archive')
        return None


def collect_init_services(approot, destroot):
    """Get treadmill init services information in node."""
    pattern = '%s/init/*/log/current' % approot

    for current in glob.glob(pattern):
        target = '%s%s' % (destroot, current)
        _safe_copy(current, target)


def collect_running_app(approot, destroot):
    """Get treadmill running application information in node."""
    pattern = '%s/running/*/run.*' % approot

    for run_log in glob.glob(pattern):
        target = '%s%s' % (destroot, run_log)
        _safe_copy(run_log, target)

    pattern = '%s/running/*/sys/*/log/current' % approot

    for current in glob.glob(pattern):
        target = '%s%s' % (destroot, current)
        _safe_copy(current, target)


def collect_sysctl(destroot):
    """Get host sysctl (related to kernel)."""
    sysctl = subproc.check_output([_SYSCTL, '-a'])
    with open('%s/sysctl' % destroot, 'w+') as f:
        f.write(sysctl)


def collect_cgroup(approot, destroot):
    """Get host treadmill cgroups inforamation."""
    src = "%s/cgroup_svc" % approot
    dest = "%s%s" % (destroot, src)

    try:
        shutil.copytree(src, dest)
    except (shutil.Error, OSError):
        _LOGGER.exception('fail to copy %s => %s', src, dest)

    pattern = '/cgroup/*/treadmill/core'
    for cgrp_core in glob.glob(pattern):
        core_dest = '%s%s' % (destroot, cgrp_core)

        try:
            shutil.copytree(cgrp_core, core_dest)
        except (shutil.Error, OSError):
            _LOGGER.exception('fail to copy %s => %s', src, dest)


def collect_localdisk(approot, destroot):
    """Get host local disk information."""
    src = '%s/localdisk_svc' % approot
    dest = '%s%s' % (destroot, src)

    try:
        shutil.copytree(src, dest)
    except (shutil.Error, OSError):
        _LOGGER.exception('fail to copy %s => %s', src, dest)

    # FIXME vgdisplay requires root


def collect_network(approot, destroot):
    """Get host network information."""
    src = '%s/network_svc' % approot
    dest = '%s%s' % (destroot, src)

    try:
        shutil.copytree(src, dest)
    except (shutil.Error, OSError):
        _LOGGER.exception('fail to copy %s => %s', src, dest)

    ifconfig = subproc.check_output([_IFCONFIG])
    with open('%s/ifconfig' % destroot, 'w') as f:
        f.write(ifconfig)


def collect_message(destroot):
    """Get messages on the host."""
    dmesg = subproc.check_output([_DMESG])
    with open('%s/dmesg' % destroot, 'w') as f:
        f.write(dmesg)

    messages = subproc.check_output(
        [_TAIL, '-n', '100', '/var/log/messages']
    )

    dest_messages = '%s/var/log/messages' % destroot
    if not os.path.exists(os.path.dirname(dest_messages)):
        os.makedirs(os.path.dirname(dest_messages))
    with open(dest_messages, 'w') as f:
        f.write(messages)
