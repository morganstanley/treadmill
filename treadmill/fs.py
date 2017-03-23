"""Implements functions for setting up container chroot and file system."""

import errno
import importlib
import logging
import os
import stat
import tarfile
import tempfile
import io

from . import exc
from . import utils
from . import subproc

if os.name != 'nt':
    import pwd

if os.name != 'nt':
    from .syscall import unshare

_LOGGER = logging.getLogger(__name__)


def rm_safe(path):
    """Removes file, ignoring the error if file does not exist."""
    try:
        os.unlink(path)
    except OSError as err:
        # If the file does not exists, it is not an error
        if err.errno == errno.ENOENT:
            pass
        else:
            raise


def mkdir_safe(path, mode=0o777):
    """Creates directory, if there is any error, aborts the process.

    :param path:
        Path to the directory to create. All intermediary folders will be
        created.
    :type path:
        ``str``
    """
    try:
        os.makedirs(path, mode=mode)

    except OSError as err:
        # If dir already exists, no problem. Otherwise raise
        if err.errno != errno.EEXIST:
            raise


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
    """Returns normalized path, aborts if path is not absolute."""
    if not os.path.isabs(path):
        raise exc.InvalidInputError(path, 'Not absolute path: %r' % path)

    return os.path.normpath(path)


def symlink_safe(link, target):
    """Create symlink to target. Atomically rename if link already exists."""
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
# chroot

def chroot_init(newroot):
    """Prepares the file system for subsequent chroot.

    - Unshares mount subsystem.
    - Creates directory that will serve as new root.

    :param newroot:
        Path to the intended root dir of the chroot environment
    :type newroot:
        ``str``
    :returns:
        Normalized path to the new root dir
    :rtype:
        ``str``
    """
    # Make sure new root is valid argument.
    newroot_norm = norm_safe(newroot)
    # Creates directory that will serve as new root.
    mkdir_safe(newroot_norm)
    # Unshare the mount namespace
    unshare.unshare(unshare.CLONE_NEWNS)
    return newroot_norm


def chroot_finalize(newroot):
    """Finalizes file system setup by chrooting into the new environment."""
    newroot_norm = norm_safe(newroot)
    os.chroot(newroot_norm)
    os.chdir('/')


###############################################################################
# mount

def mount_filesystem(block_dev, target_dir):
    """Mount filesystem on target directory.

    :param block_dev:
        Block device to mount
    """
    subproc.check_call(['mount', '-n', block_dev, target_dir])


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


def mount_tmpfs(newroot, path, size):
    """Mounts directory on tmpfs."""
    while path.startswith('/'):
        path = path[1:]
    subproc.check_call(['mount', '-n', '-o', 'size=%s' % size,
                        '-t', 'tmpfs', 'tmpfs', os.path.join(newroot, path)])


def _iter_plugins():
    """Iterate over configured plugins."""
    fsplugins = importlib.import_module('treadmill.plugins.fs')
    for path in fsplugins.__path__:
        _LOGGER.info('Processing plugins: %s', path)
        for filename in os.listdir(path):
            if filename == '__init__.py':
                continue

            if not filename.endswith('.py'):
                continue

            name = 'treadmill.plugins.fs.' + filename[:-3]
            _LOGGER.info('Loading: %s', name)
            mod = importlib.import_module(name)
            yield mod


def init_plugins(rootdir):
    """Initialize plugins."""
    # XXX: for mod in _iter_plugins():
    # XXX:    mod.init(rootdir)


def configure_plugins(rootdir, newroot, app):
    """Configure each plugin in pre-chrooted environment."""
    # Load fs plugins
    # XXX: for mod in _iter_plugins():
    # XXX:   mod.configure(rootdir, newroot, app)


###############################################################################
# Container layout

def make_rootfs(newroot, proid):
    """Initializes directory structure for the container in a new root.

    - Bind directories in parent / (with exceptions - see below.)
    - Skip /tmp, create /tmp in the new root with correct permissions.
    - Selectively create / bind /var.
      - /var/tmp (new)
      - /var/logs (new)
      - /var/spool - create empty with dirs.
    - Bind everything in /var, skipping /spool/tickets

    :param newroot:
        Path where the new root device will be mounted
    :type newroot:
        ``str``
    :param proid:
        Proid who will own the new root
    :type proid:
        ``str``
    """
    newroot_norm = norm_safe(newroot)
    mounts = [
        '/bin',
        '/common',
        '/dev',
        '/etc',
        '/lib',
        '/lib64',
        '/mnt',
        '/proc',
        '/sbin',
        '/srv',
        '/sys',
        '/usr',
        '/var/tmp/treadmill/env',
        '/var/tmp/treadmill/spool',
    ]

    emptydirs = [
        '/tmp',
        '/opt',
        '/var/spool/keytabs',
        '/var/spool/tickets',
        '/var/spool/tokens',
        '/var/tmp',
        '/var/tmp/cores',
    ]

    stickydirs = [
        '/tmp',
        '/opt',
        '/var/spool/keytabs',
        '/var/spool/tickets',
        '/var/spool/tokens',
        '/var/tmp',
        '/var/tmp/cores/',
    ]

    for mount in mounts:
        if os.path.exists(mount):
            mount_bind(newroot_norm, mount)

    for directory in emptydirs:
        mkdir_safe(newroot_norm + directory)

    for directory in stickydirs:
        os.chmod(newroot_norm + directory, 0o777 | stat.S_ISVTX)

    # Mount .../tickets .../keytabs on tempfs, so that they will be cleaned
    # up when the container exits.
    #
    # TODO: Do we need to have a single mount for all tmpfs dirs?
    for tmpfsdir in ['/var/spool/tickets', '/var/spool/keytabs',
                     '/var/spool/tokens']:
        mount_tmpfs(newroot_norm, tmpfsdir, '4M')

    userdirs = [
        '/home',
    ]

    pwnam = pwd.getpwnam(proid)
    for directory in userdirs:
        mkdir_safe(newroot_norm + directory)
        os.chown(newroot_norm + directory, pwnam.pw_uid, pwnam.pw_gid)


###############################################################################
# Block device

def dev_maj_min(block_dev):
    """Returns major/minor device numbers for the given block device."""
    dev_stat = os.stat(os.path.realpath(block_dev))
    return (os.major(dev_stat.st_rdev), os.minor(dev_stat.st_rdev))


###############################################################################
# Filesystem management
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
        ``str`` or File
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
    assert compression is None or compression in ['gzip', 'bzip2']
    assert isinstance(target, str) or isinstance(target, io.IOBase)

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
    if isinstance(target, str):
        mode = 'w:' + mode
        target += ext
        return _tar_impl(sources, name=target, mode=mode)
    else:
        mode = 'w|' + mode
        return _tar_impl(sources, fileobj=target, mode=mode)


def _tar_impl(sources, **args):
    """ implementation of tar
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
