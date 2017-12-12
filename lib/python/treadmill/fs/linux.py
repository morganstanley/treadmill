"""Linux specific mount and filesystem utilities and wrappers.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import io
import logging
import os
import re

import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order


from treadmill import exc
from treadmill import fs
from treadmill import subproc
from treadmill.syscall import mount

_LOGGER = logging.getLogger(__name__)

_UUID_RE = re.compile(r'.*UUID="(.*?)".*')


###############################################################################
# Mount utilities

def umount_filesystem(target_dir):
    """umount filesystem on target directory.
    """
    return mount.unmount(target=target_dir)


def mount_filesystem(block_dev, target_dir, fs_type='ext4'):
    """Mount filesystem on target directory.

    :param block_dev:
        Block device to mount
    """
    return mount.mount(
        source=block_dev,
        target=target_dir,
        fs_type=fs_type,
        mnt_flags=(
            mount.MS_NOATIME,
            mount.MS_NODIRATIME,
        )
    )


def mount_bind(newroot, target, source=None, recursive=True, read_only=True):
    """Bind mounts `source` to `newroot/target` so that `source` is accessed
    when reaching `newroot/target`.

    If a directory, the source will be mounted using --rbind.
    """
    # Ensure root directory exists
    if not os.path.exists(newroot):
        raise exc.ContainerSetupError('Path %r does not exist' % newroot)

    if source is None:
        source = target

    target = fs.norm_safe(target)
    source = fs.norm_safe(source)

    # Make sure target directory exists.
    if not os.path.exists(source):
        raise exc.ContainerSetupError('Source path %r does not exist' % source)

    mnt_flags = [mount.MS_BIND]

    # Use --rbind for directories and --bind for files.
    if recursive and os.path.isdir(source):
        mnt_flags.append(mount.MS_REC)

    # Strip leading /, ensure that mount is relative path.
    while target.startswith('/'):
        target = target[1:]

    # Create mount directory, make sure it does not exists.
    target_fp = os.path.join(newroot, target)
    if os.path.isdir(source):
        fs.mkdir_safe(target_fp)
    else:
        fs.mkfile_safe(target_fp)

    res = mount.mount(source=source, target=target_fp,
                      fs_type=None, mnt_flags=mnt_flags)
    if read_only:
        res = mount.mount(source=None, target=target_fp,
                          fs_type=None, mnt_flags=(mount.MS_BIND,
                                                   mount.MS_RDONLY,
                                                   mount.MS_REMOUNT))

    return res


def mount_proc(newroot, target='proc'):
    """Mounts /proc directory on newroot.
    """
    while target.startswith('/'):
        target = target[1:]

    return mount.mount(
        source='proc',
        target=os.path.join(newroot, target),
        fs_type='proc'
    )


def mount_sysfs(newroot, target='sys', read_only=True):
    """Mounts /sysfs directory on newroot.
    """
    while target.startswith('/'):
        target = target[1:]

    mnt_flags = []
    if read_only:
        mnt_flags.append(mount.MS_RDONLY)

    return mount.mount(
        source='sysfs',
        target=os.path.join(newroot, target),
        fs_type='sysfs',
        mnt_flags=mnt_flags
    )


def mount_tmpfs(newroot, target, size=None):
    """Mounts directory on tmpfs.
    """
    while target.startswith('/'):
        target = target[1:]

    mnt_opts = {}
    if size is not None:
        mnt_opts['size'] = size

    return mount.mount(
        source='tmpfs',
        target=os.path.join(newroot, target),
        fs_type='tmpfs',
        mnt_flags=(
            mount.MS_NOATIME,
            mount.MS_NODIRATIME,
        ),
        mnt_opts=mnt_opts
    )


###############################################################################
# Filesystem management

def blk_fs_create(block_dev):
    """Create a new filesystem for an application of a given size formatted as
    ext4.

    :param block_dev:
        Block device where to create the new filesystem
    :type block_dev:
        ``str``
    """
    subproc.check_call(
        [
            'mke2fs',
            '-F',
            '-E', 'lazy_itable_init=1,nodiscard',
            '-O', 'uninit_bg',
            block_dev
        ]
    )


def blk_fs_test(block_dev):
    """Test the existence of a filesystem on a given block device.

    We essentially try to read the superblock and assume no filesystem if we
    fail.

    :param block_dev:
        Block device where to create the new filesystem.
    :type block_dev:
        ``str``
    :returns ``bool``:
        True if the block device contains a filesystem.
    """
    res = subproc.call(
        [
            'tune2fs',
            '-l',
            block_dev
        ]
    )
    return bool(res == 0)


def blk_fs_info(block_dev):
    """Returns blocks group information for the filesystem present on
    block_dev.

    :param block_dev:
        Block device for the filesystem info to query.
    :type block_dev:
        ``str``
    :returns:
        Blocks group information.
    :rtype:
        ``dict``
    """
    res = {}

    # TODO: it might worth to convert the appropriate values to int, date etc.
    #       in the result.
    try:
        output = subproc.check_output(['dumpe2fs', '-h', block_dev])
    except subprocess.CalledProcessError:
        return res

    for line in output.split(os.linesep):
        if not line.strip():
            continue

        key, val = line.split(':', 1)
        res[key.lower()] = val.strip()

    return res


def blk_uuid(block_dev):
    """Get device uuid
    """
    output = subproc.check_output(['blkid', block_dev])
    match_obj = _UUID_RE.match(output)
    if match_obj is None:
        raise ValueError('Invalid device: %s' % block_dev)
    else:
        return match_obj.group(1)


def blk_maj_min(block_dev):
    """Returns major/minor device numbers for the given block device.
    """
    dev_stat = os.stat(os.path.realpath(block_dev))
    return os.major(dev_stat.st_rdev), os.minor(dev_stat.st_rdev)


###############################################################################
# Major:Minor utilities

def maj_min_to_blk(major, minor):
    """Returns the block device name to the major:minor numbers in the param.

    :param major:
        The major number of the device
    :param minor:
        The minor number of the device
    :returns:
        Block device name.
    :rtype:
        ``str``
    """
    # TODO: Reimplement using /proc/partition
    maj_min = '{}:{}'.format(major, minor)
    block_dev = None
    for sys_path in glob.glob(os.path.join(os.sep, 'sys', 'class', 'block',
                                           '*', 'dev')):
        with io.open(sys_path) as f:
            if f.read().strip() == maj_min:
                block_dev = '/dev/{}'.format(sys_path.split(os.sep)[-2])
                break

    return block_dev


def maj_min_from_path(path):
    """Returns major/minor device numbers for the given path.
    """
    dev_stat = os.stat(os.path.realpath(path))
    return os.major(dev_stat.st_dev), os.minor(dev_stat.st_dev)


###############################################################################

__all__ = [
    'blk_fs_create',
    'blk_fs_info',
    'blk_fs_test',
    'blk_maj_min',
    'blk_uuid',
    'maj_min_from_path',
    'maj_min_to_blk',
    'mount_bind',
    'mount_filesystem',
    'mount_tmpfs',
    'umount_filesystem',
]
