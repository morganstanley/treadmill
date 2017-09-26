"""File system utilities such as making dirs/files and mounts etc.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import glob
import io
import logging
import os
import re
import stat
import tarfile
import tempfile

import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import exc
from treadmill import osnoop
from treadmill import utils
from treadmill import subproc


_LOGGER = logging.getLogger(__name__)

_UUID_RE = re.compile(r'.*UUID="(.*?)".*')


def rm_safe(path):
    """Removes file, ignoring the error if file does not exist.
    """
    try:
        os.unlink(path)
    except OSError as err:
        # If the file does not exists, it is not an error
        if err.errno == errno.ENOENT:
            pass
        else:
            raise


def write_safe(filename, func, mode='wb', prefix='tmp', permission=None):
    """Safely write file

    :param filename:
        full path of file
    :param func:
        what to do with the file descriptor, signature func(fd)
    :param mode:
        same as tempfile.NamedTemporaryFile
    :param prefix:
        same as tempfile.NamedTemporaryFile
    :param permission:
        file permission
    """
    dirname = os.path.dirname(filename)
    try:
        os.makedirs(dirname)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise
    with tempfile.NamedTemporaryFile(dir=dirname,
                                     delete=False,
                                     prefix=prefix,
                                     mode=mode) as tmpfile:
        if permission is not None and os.name == 'posix':
            os.fchmod(tmpfile.fileno(), permission)
        func(tmpfile)
    os.rename(tmpfile.name, filename)


def mkdir_safe(path, mode=0o777):
    """Creates directory, if there is any error, aborts the process.

    :param path:
        Path to the directory to create. All intermediary folders will be
        created.
    :type path:
        ``str``
    :return:
        ``True`` if the directory was created
    :rtype:
        ``Boolean``
    """
    try:
        os.makedirs(path, mode=mode)
        return True
    except OSError as err:
        # If dir already exists, no problem. Otherwise raise
        if err.errno != errno.EEXIST:
            raise
        return False


def mkfile_safe(path):
    """Creates empty file at the given path if it does not exist

    :param path:
        Path to the file to create. All intermediary folders will be
        created.
    :type path:
        ``str``
    """
    mkdir_safe(os.path.dirname(path))
    create_excl(path, size=0)


def norm_safe(path):
    """Returns normalized path, aborts if path is not absolute.
    """
    if not os.path.isabs(path):
        raise exc.InvalidInputError(path, 'Not absolute path: %r' % path)

    return os.path.normpath(path)


def symlink_safe(link, target):
    """Create symlink to target. Atomically rename if link already exists.
    """
    tmp_link = tempfile.mktemp(dir=os.path.dirname(link))
    os.symlink(target, tmp_link)
    os.rename(tmp_link, link)


def create_excl(filename, size=0, mode=(stat.S_IRUSR | stat.S_IWUSR)):
    """Create a file if it doesn't already exists

    Perform a open/3 limited to the user and create|excl.
    Securely create a file with S_IRUSR|S_IWUSR permissions and truncate
    to a specific size.

    :param filename:
        Path name to the file which is to be created.
    :type filename:
        ``str``
    :param size:
        Size in bytes of the new file (defaults to 0)
    :type size:
        ``int``
    :param mode:
        Permission flag for the new file (defaults to read|write to the owner
        only)
    :type mode:
        ``int``
    :returns:
        ``bool`` -- True if the file creation was successful, False if the file
        already existed.
    """
    openflags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = -1
        orig_umask = os.umask(0)
        fd = os.open(filename, openflags, mode)
        with os.fdopen(fd, 'wb') as f:
            f.truncate(size)
            return True
    except OSError as err:
        if fd != -1:
            os.close(fd)
        # If file already exists, no problem. Otherwise raise
        if err.errno != errno.EEXIST:
            raise
    finally:
        os.umask(orig_umask)

    return False


###############################################################################
# mount

@osnoop.windows
def umount_filesystem(target_dir):
    """umount filesystem on target directory.
    """
    subproc.check_call(['umount', '-n', '-f', target_dir])


@osnoop.windows
def mount_filesystem(block_dev, target_dir):
    """Mount filesystem on target directory.

    :param block_dev:
        Block device to mount
    """
    subproc.check_call(['mount', '-n', block_dev, target_dir])


@osnoop.windows
def mount_bind(newroot, mount, target=None, bind_opt=None):
    """Mounts directory in the new root.

    Call to mount should be done before chrooting into new root.

    Unless specified, the target directory will be mounted using --rbind.
    """
    # Ensure root directory exists
    if not os.path.exists(newroot):
        raise exc.ContainerSetupError('Path %s does not exist' % newroot)

    if target is None:
        target = mount

    mount = norm_safe(mount)
    target = norm_safe(target)

    # Make sure target directory exists.
    if not os.path.exists(target):
        raise exc.ContainerSetupError('Target path %s does not exist' % target)

    # If bind_opt is not explicit, use --rbind for directories and
    # --bind for files.
    if bind_opt is None:
        if os.path.isdir(target):
            bind_opt = '--rbind'
        else:
            bind_opt = '--bind'

    # Strip leading /, ensure that mount is relative path.
    while mount.startswith('/'):
        mount = mount[1:]

    # Create mount directory, make sure it does not exists.
    mount_fp = os.path.join(newroot, mount)
    if os.path.isdir(target):
        mkdir_safe(mount_fp)
    else:
        mkfile_safe(mount_fp)

    subproc.check_call(
        [
            'mount',
            '-n',
            bind_opt,
            target,
            mount_fp
        ]
    )


@osnoop.windows
def mount_tmpfs(newroot, path, size):
    """Mounts directory on tmpfs.
    """
    while path.startswith('/'):
        path = path[1:]
    subproc.check_call(['mount', '-n', '-o', 'size=%s' % size,
                        '-t', 'tmpfs', 'tmpfs', os.path.join(newroot, path)])


###############################################################################
# Block device

@osnoop.windows
def dev_maj_min(block_dev):
    """Returns major/minor device numbers for the given block device.
    """
    dev_stat = os.stat(os.path.realpath(block_dev))
    return os.major(dev_stat.st_rdev), os.minor(dev_stat.st_rdev)


###############################################################################
# Filesystem management

@osnoop.windows
def create_filesystem(block_dev):
    """Create a new filesystem for an application of a given size formatted as
    ext3.

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


@osnoop.windows
def test_filesystem(block_dev):
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


@osnoop.windows
def archive_filesystem(block_dev, rootdir, archive, files):
    """Archive the filesystem of an application

    :param block_dev:
        Block device from where to archive the new filesystem
    :type block_dev:
        ``str``
    :param rootdir:
        Path to a directory where to mount the root device
    :type rootdir:
        ``str``
    :param archive:
        Path to the archive file to create
    :type archive:
        ``str``
    :param files:
        List of files and folders to include in the archive
        relative to rootdir. This is input list of files to
        tar.
    :type list:
        ``str``
    """
    if not files:
        _LOGGER.info('Nothing to archive.')
        return True

    if not os.path.exists(rootdir):
        _LOGGER.error('Root device directory does not exist: %s', rootdir)
        return False

    archive_cmd = '{tm_root}/sbin/archive_container.sh'.format(
        tm_root=utils.rootdir()
    )

    arguments = ['unshare',
                 '--mount',
                 archive_cmd,
                 block_dev,
                 # rootdir
                 os.path.realpath(rootdir),
                 # archive
                 os.path.realpath(archive)]

    # Make sure files are relative path.
    safe_files = [filename.lstrip('/') for filename in files]
    arguments.extend(safe_files)

    result = subproc.call(arguments)
    return result == 0


def tar(target, sources, compression=None):
    """This adds or creates a tarball with the provided folder.

    If the tar exists it will append, otherwise it will create the tar.

    The folder specified will be added to the root of the tar.
    For example, if fs.tar('tar.tar', '/foo') is called, it
    will add the contents (including subfolders) in /foo to / in the tar.

    :param target:
        target tar file name or file object
    :type target:
        ``str`` or file
    :param sources:
        list of folders or file / a single foldler or file
    :type sources:
        ``list`` or ``str``
    :param compression:
        compression mode
    :type compression:
        ``str``
    :returns:
        target file name with compression postfix
    :rtype:
        ``str``
    """
    assert compression in [None, 'gzip', 'bzip2']

    if compression == 'gzip':
        mode = 'gz'
        ext = '.gz'
    elif compression == 'bzip2':
        mode = 'bz2'
        ext = '.bz2'
    else:
        mode = ''
        ext = ''

    # if target file is not given, we write as stream mode
    if isinstance(target, six.string_types):
        mode = 'w:' + mode
        target += ext
        return _tar_impl(sources, name=target, mode=mode)
    else:
        mode = 'w|' + mode
        return _tar_impl(sources, fileobj=target, mode=mode)


def _tar_impl(sources, **args):
    """implementation of tar.
    """
    try:
        with tarfile.open(**args) as archive:
            # Make sure the folder doesn't end in '/'
            if isinstance(sources, list):
                for source in sources:
                    archive.add(source.rstrip('/'), '/')
            else:
                archive.add(sources.rstrip('/'), '/')

    except:  # pylint: disable=W0702
        _LOGGER.exception('Error taring up files')
        raise

    return archive


@osnoop.windows
def read_filesystem_info(block_dev):
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


@osnoop.windows
def device_uuid(block_dev):
    """Get device uuid
    """
    output = subproc.check_output(['blkid', block_dev])
    match_obj = _UUID_RE.match(output)
    if match_obj is None:
        raise ValueError('Invalid device: %s' % block_dev)
    else:
        return match_obj.group(1)


@osnoop.windows
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
    maj_min = '{}:{}'.format(major, minor)
    block_dev = None
    for sys_path in glob.glob(os.path.join(os.sep, 'sys', 'class', 'block',
                                           '*', 'dev')):
        with io.open(sys_path) as f:
            if f.read().strip() == maj_min:
                block_dev = '/dev/{}'.format(sys_path.split(os.sep)[-2])
                break

    return block_dev


@osnoop.windows
def path_to_maj_min(path):
    """Returns major/minor device numbers for the given path.
    """
    dev_stat = os.stat(os.path.realpath(path))
    return os.major(dev_stat.st_dev), os.minor(dev_stat.st_dev)
