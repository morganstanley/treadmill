"""Collect Treadmill node information after a crash.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import importlib
import io
import logging
import os
import shutil
import socket
import tempfile

from treadmill import fs
from treadmill import subproc
from treadmill import utils

_LOGGER = logging.getLogger(__name__)

_IFCONFIG = 'ifconfig'
_SYSCTL = 'sysctl'
_DMESG = 'dmesg'
_TAIL = 'tail'
_LVM = 'lvm'
_VGDISPLAY = 'vgdisplay'
_LVDISPLAY = 'lvdisplay'

try:
    _UPLOADER = importlib.import_module(
        'treadmill.plugins.postmortem_uploader'
    )
except ImportError:
    _UPLOADER = None


def run(treadmill_root, upload_url=None):
    """Run postmortem"""
    filetime = utils.datetime_utcnow().strftime('%Y%m%d_%H%M%SUTC')
    hostname = socket.gethostname()
    postmortem_file_base = os.path.join(
        '/tmp', '{0}-{1}.tar'.format(hostname, filetime)
    )

    postmortem_file = collect(
        treadmill_root,
        postmortem_file_base
    )
    os.chmod(postmortem_file, 0o644)
    _LOGGER.info('generated postmortem file: %r', postmortem_file)

    if _UPLOADER is not None:
        _UPLOADER.upload(postmortem_file, upload_url)


def _safe_copy(src, dest):
    """Copy file from src to dest if need, generate sub directory for dest"""
    parent = os.path.dirname(dest)

    if not os.path.exists(parent):
        os.makedirs(parent)

    try:
        shutil.copyfile(src, dest)
        _LOGGER.debug('file copied %s => %s', src, dest)
    except OSError:
        _LOGGER.warning('skip %s => %s', src, dest)


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

    pattern = '%s/running/*/data/sys/*/data/log/current' % approot

    for current in glob.glob(pattern):
        target = '%s%s' % (destroot, current)
        _safe_copy(current, target)


def collect_sysctl(destroot):
    """Get host sysctl (related to kernel)."""
    sysctl = subproc.check_output([_SYSCTL, '-a'])
    with io.open('%s/sysctl' % destroot, 'w') as f:
        f.write(sysctl)


def collect_cgroup(approot, destroot):
    """Get host treadmill cgroups inforamation."""
    src = "%s/cgroup_svc" % approot
    dest = "%s%s" % (destroot, src)

    try:
        shutil.copytree(src, dest)
    except (shutil.Error, OSError):
        _LOGGER.warning('skip %s => %s', src, dest)

    pattern = '/cgroup/*/treadmill/core'
    for cgrp_core in glob.glob(pattern):
        core_dest = '%s%s' % (destroot, cgrp_core)

        try:
            shutil.copytree(cgrp_core, core_dest)
        except (shutil.Error, OSError):
            _LOGGER.warning('skip %s => %s', src, dest)


def collect_localdisk(approot, destroot):
    """Get host local disk information."""
    src = '%s/localdisk_svc' % approot
    dest = '%s%s' % (destroot, src)

    try:
        shutil.copytree(src, dest)
    except (shutil.Error, OSError):
        _LOGGER.warning('skip %s => %s', src, dest)

    vg_info = subproc.check_output([_LVM, _VGDISPLAY, 'treadmill'])
    lv_info = subproc.check_output([_LVM, _LVDISPLAY, 'treadmill'])
    with io.open('%s/lvm' % destroot, 'w') as f:
        f.write('%s\n%s' % (vg_info, lv_info))


def collect_network(approot, destroot):
    """Get host network information."""
    src = '%s/network_svc' % approot
    dest = '%s%s' % (destroot, src)

    try:
        shutil.copytree(src, dest)
    except (shutil.Error, OSError):
        _LOGGER.warning('skip %s => %s', src, dest)

    ifconfig = subproc.check_output([_IFCONFIG])
    with io.open('%s/ifconfig' % destroot, 'w') as f:
        f.write(ifconfig)


def collect_message(destroot):
    """Get messages on the host."""
    dmesg = subproc.check_output([_DMESG])
    with io.open('%s/dmesg' % destroot, 'w') as f:
        f.write(dmesg)

    messages = subproc.check_output(
        [_TAIL, '-n', '100', '/var/log/messages']
    )

    dest_messages = '%s/var/log/messages' % destroot
    if not os.path.exists(os.path.dirname(dest_messages)):
        os.makedirs(os.path.dirname(dest_messages))
    with io.open(dest_messages, 'w') as f:
        f.write(messages)
