"""Linux specific mount and filesystem utilities and wrappers.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import fnmatch
import glob
import io
import logging
import os
import re

from treadmill import exc
from treadmill import fs
from treadmill import subproc
from treadmill.syscall import mount

_LOGGER = logging.getLogger(__name__)

_UUID_RE = re.compile(r'\sUUID="([a-zA-Z0-9-]+)"\s')


###############################################################################
# Mount utilities
from treadmill.syscall.mount import mount as mount_filesystem


def umount_filesystem(target_dir, lazy=False):
    """umount filesystem on target directory.
    """
    if lazy:
        return mount.unmount(target=target_dir, mnt_flags=(mount.MNT_DETACH,))
    else:
        return mount.unmount(target=target_dir)


def mount_move(target, source):
    """Move a mount from one to a point to another.
    """
    return mount.mount(source=source, target=target,
                       fs_type=None, mnt_flags=[mount.MS_MOVE])


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

    if res == 0 and read_only:
        res = mount.mount(source=None, target=target_fp,
                          fs_type=None, mnt_flags=(mount.MS_BIND,
                                                   mount.MS_RDONLY,
                                                   mount.MS_REMOUNT))

    return res


def mount_procfs(newroot, target='/proc'):
    """Mounts procfs on directory.
    """
    while target.startswith('/'):
        target = target[1:]

    mnt_flags = [
        mount.MS_NODEV,
        mount.MS_NOEXEC,
        mount.MS_NOSUID,
        mount.MS_RELATIME,
    ]

    return mount.mount(
        source='proc',
        target=os.path.join(newroot, target),
        fs_type='proc',
        mnt_flags=mnt_flags,
    )


def mount_sysfs(newroot, target='/sys'):
    """Mounts sysfs on directory.
    """
    while target.startswith('/'):
        target = target[1:]

    mnt_flags = [
        mount.MS_NODEV,
        mount.MS_NOEXEC,
        mount.MS_NOSUID,
        mount.MS_RELATIME,
    ]

    return mount.mount(
        source='sysfs',
        target=os.path.join(newroot, target),
        fs_type='sysfs',
        mnt_flags=mnt_flags,
    )


def mount_tmpfs(newroot, target, nodev=True, noexec=True, nosuid=True,
                relatime=True, **mnt_opts):
    """Mounts directory on tmpfs.
    """
    while target.startswith('/'):
        target = target[1:]

    mnt_flags = [
        (nodev, mount.MS_NODEV),
        (noexec, mount.MS_NOEXEC),
        (nosuid, mount.MS_NOSUID),
        (relatime, mount.MS_RELATIME),
    ]

    return mount.mount(
        source='tmpfs',
        target=os.path.join(newroot, target),
        fs_type='tmpfs',
        mnt_flags=[mnt_flag for flag, mnt_flag in mnt_flags if flag],
        **mnt_opts
    )


def mount_devpts(newroot, target, **mnt_opts):
    """Mounts directory on devpts.
    """
    while target.startswith('/'):
        target = target[1:]

    mount.mount(
        source='devpts',
        target=os.path.join(newroot, target),
        fs_type='devpts',
        mnt_flags=(
            mount.MS_NOSUID,
            mount.MS_NOEXEC
        ),
        **mnt_opts
    )

    os.chmod(os.path.join(newroot, target, 'ptmx'), 0o666)


def mount_mqueue(newroot, target, **mnt_opts):
    """Mounts directory on mqueue.
    """
    while target.startswith('/'):
        target = target[1:]

    return mount.mount(
        source='mqueue',
        target=os.path.join(newroot, target),
        fs_type='mqueue',
        mnt_flags=(
            mount.MS_NOSUID,
            mount.MS_NODEV,
            mount.MS_NOEXEC
        ),
        **mnt_opts
    )


class MountEntry:
    """Mount table entry data.
    """

    __slots__ = (
        'source',
        'target',
        'fs_type',
        'mnt_opts',
        'mount_id',
        'parent_id'
    )

    def __init__(self, source, target, fs_type, mnt_opts,
                 mount_id, parent_id):
        self.source = source
        self.target = target
        self.fs_type = fs_type
        self.mnt_opts = mnt_opts
        self.mount_id = int(mount_id)
        self.parent_id = int(parent_id)

    def __repr__(self):
        return (
            '{name}(source={src!r}, target={target!r}, '
            'fs_type={fs_type!r}, mnt_opts={mnt_opts!r})'
        ).format(
            name=self.__class__.__name__,
            src=self.source,
            target=self.target,
            fs_type=self.fs_type,
            mnt_opts=self.mnt_opts
        )

    def __lt__(self, other):
        """Ordering is based on mount target.
        """
        return self.target < other.target

    def __eq__(self, other):
        """Equality is defined as the equality of the mount entry's attributes.
        """
        res = (
            (self.mount_id == other.mount_id) and
            (self.parent_id == other.parent_id) and
            (self.source == other.source) and
            (self.target == other.target) and
            (self.fs_type == other.fs_type) and
            (self.mnt_opts == other.mnt_opts)
        )
        return res

    @classmethod
    def mount_entry_parse(cls, mount_entry_line):
        """Create a `:class:MountEntry from a mountinfo data line.

        The file contains lines of the form:

            36 35 98:0 /mnt1 /mnt2 rw,noatime master:1
                                            - ext3 /dev/root rw,errors=continue
            (1)(2)(3)   (4)   (5)      (6)      (7)
                                           (8) (9)   (10)         (11)

        The numbers in parentheses are labels for the descriptions
        below:

            (1)  mount ID: a unique ID for the mount (may be reused after
                 umount(2)).

            (2)  parent ID: the ID of the parent mount (or of self for the
                 root of this mount namespace's mount tree).

                 If the parent mount point lies outside the process's root
                 directory (see chroot(2)), the ID shown here won't have a
                 corresponding record in mountinfo whose mount ID (field
                 1) matches this parent mount ID (because mount points
                 that lie outside the process's root directory are not
                 shown in mountinfo).  As a special case of this point,
                 the process's root mount point may have a parent mount
                 (for the initramfs filesystem) that lies outside the
                 process's root directory, and an entry for that mount
                 point will not appear in mountinfo.

            (3)  major:minor: the value of st_dev for files on this
                 filesystem (see stat(2)).

            (4)  root: the pathname of the directory in the filesystem
                 which forms the root of this mount.

            (5)  mount point: the pathname of the mount point relative to
                 the process's root directory.

            (6)  mount options: per-mount options.

            (7)  optional fields: zero or more fields of the form
                 "tag[:value]"; see below.

            (8)  separator: the end of the optional fields is marked by a
                 single hyphen.

            (9)  filesystem type: the filesystem type in the form
                 "type[.subtype]".

            (10) mount source: filesystem-specific information or "none".

            (11) super options: per-superblock options.

        """
        mount_entry_line = mount_entry_line.strip().split(' ')

        (
            mount_id,
            parent_id,
            _major_minor,
            _parent_path,
            target,
            mnt_opts
        ), data = mount_entry_line[:6], mount_entry_line[6:]

        fields = []
        while data[0] != '-':
            fields.append(data.pop(0))

        (
            _,
            fs_type,
            source,
            mnt_opts2
        ) = data

        mnt_opts = set(mnt_opts.split(',') + mnt_opts2.split(','))

        return cls(source, target, fs_type, mnt_opts, mount_id, parent_id)


def list_mounts(mountinfo='/proc/self/mountinfo'):
    """Read the current process' mounts.
    """
    mounts = []

    try:
        with io.open(mountinfo, 'r') as mf:
            mounts_lines = mf.readlines()

    except EnvironmentError as err:
        if err.errno == errno.ENOENT:
            _LOGGER.warning('Unable to read "%s": %s', mountinfo, err)
            return mounts
        else:
            raise

    for mounts_line in mounts_lines:
        mounts.append(MountEntry.mount_entry_parse(mounts_line))

    return mounts


###############################################################################
def generate_sorted_mounts(mountinfo=None):
    """Get a list of sorted mount entries from down to top
    """
    # create a dict tree for mount_entries
    # format: mount_id: mount_entry
    if mountinfo:
        mount_entries = list_mounts(mountinfo)
    else:
        mount_entries = list_mounts()

    current_mounts = {
        mount_entry.mount_id: mount_entry
        for mount_entry in mount_entries
    }

    # We need to iterate over mounts in "layering" order.
    mount_parents = {}
    for mount_entry in current_mounts.values():
        mount_parents.setdefault(
            mount_entry.parent_id,
            []
        ).append(mount_entry.mount_id)

    sorted_mounts = sorted(
        [
            (
                len(mount_parents.get(mount_entry.mount_id, [])),
                mount_entry
            )
            for mount_entry in current_mounts.values()
        ]
    )
    return [mount[1] for mount in sorted_mounts]


def cleanup_mounts(whitelist_patterns, ignore_exc=False):
    """Prune all mount points except whitelisted ones.

    :param ``bool`` ignore_exc:
        If True, proceed in a best effort, only logging when unmount fails.
    """
    _LOGGER.info('Removing all mounts except %r', whitelist_patterns)
    sorted_mounts = generate_sorted_mounts()

    for mount_entry in sorted_mounts:
        is_valid = any(
            fnmatch.fnmatchcase(mount_entry.target, whitelist_pat)
            for whitelist_pat in whitelist_patterns
        )
        if is_valid:
            _LOGGER.info('Mount preserved: %r', mount_entry)
        elif ignore_exc:
            try:
                umount_filesystem(mount_entry.target)
            except OSError as err:
                _LOGGER.warning('Failed to umount %r: %s',
                                mount_entry.target, err)
        else:
            umount_filesystem(mount_entry.target)


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
    except subproc.CalledProcessError:
        return res

    for line in output.split(os.linesep):
        if not line.strip():
            continue

        key, val = line.split(':', 1)
        res[key.lower()] = val.strip()

    return res


def blk_uuid(block_dev):
    """Get device uuid.

    :returns:
        ``str | None`` - Device UUID or None if it does not have one.
    """
    try:
        output = subproc.check_output(['blkid', block_dev])
    except subproc.CalledProcessError:
        _LOGGER.warning('Device %r does not have a UUID', block_dev)
        return None
    match_obj = _UUID_RE.search(output)
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
    'list_mounts',
    'maj_min_from_path',
    'maj_min_to_blk',
    'mount_bind',
    'mount_filesystem',
    'mount_procfs',
    'mount_sysfs',
    'mount_tmpfs',
    'umount_filesystem',
]
