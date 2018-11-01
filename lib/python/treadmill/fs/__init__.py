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
import stat  # pylint: disable=wrong-import-order
import shutil
import sys
import tarfile
import tempfile

import six

if os.name == 'nt':
    # E0401: Unable to import windows only pakages
    import win32api  # pylint: disable=E0401
    import win32con  # pylint: disable=E0401

from treadmill import exc
from treadmill import subproc

_LOGGER = logging.getLogger(__name__)


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


def rmtree_safe(path):
    """Remove directory, ignoring if directory does not exist."""
    try:
        shutil.rmtree(path)
    except OSError as err:
        # If the file does not exists, it is not an error
        if err.errno == errno.ENOENT:
            pass
        else:
            raise


def rm_children_safe(path):
    """Remove directory contents."""
    for f in glob.glob(os.path.join(path, '*')):
        rm_safe(f)


def replace(path_from, path_to):
    """Temp replace/rename for windows."""
    if sys.version_info[0] < 3:
        # TODO: os.rename cannot replace on windows
        # (use os.replace in python 3.4)
        if os.name == 'nt':
            win32api.MoveFileEx(path_from, path_to,
                                win32con.MOVEFILE_REPLACE_EXISTING)
        else:
            os.rename(path_from, path_to)
    else:
        os.replace(path_from, path_to)


def write_safe(filename, func, mode='wb', prefix='tmp', permission=None,
               owner=None):
    """Safely write file.

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
    :param owner
        file owner (uid, gui) tuple
    """
    dirname = os.path.dirname(filename)
    try:
        os.makedirs(dirname)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise
    try:
        with tempfile.NamedTemporaryFile(dir=dirname,
                                         delete=False,
                                         prefix=prefix,
                                         mode=mode) as tmpfile:
            if permission is not None and os.name == 'posix':
                os.fchmod(tmpfile.fileno(), permission)

            func(tmpfile)

            if owner:
                uid, gid = owner
                os.fchown(tmpfile.fileno(), uid, gid)

        replace(tmpfile.name, filename)
    finally:
        rm_safe(tmpfile.name)


def mkdir_safe(path, mode=0o777):
    """Creates directory, if there is any error, aborts the process.

    :param ``str`` path:
        Path to the directory to create. All intermediary folders will be
        created.
    :return ``Bool``:
        ``True`` - if the directory was created.
        ``False`` - if the directory already existed.
    """
    try:
        os.makedirs(path, mode=mode)
        return True
    except OSError as err:
        # If dir already exists, no problem. Otherwise raise
        if err.errno == errno.EEXIST and os.path.isdir(path):
            return False
        else:
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
    """Returns normalized path, aborts if path is not absolute.
    """
    if not os.path.isabs(path):
        raise exc.InvalidInputError(path, 'Not absolute path: %r' % path)

    return os.path.normpath(path)


def symlink_safe(link, target):
    """Create symlink to target. Atomically rename if link already exists.
    """
    tmp_link = tempfile.mktemp(prefix='.tmp', dir=os.path.dirname(link))
    os.symlink(target, tmp_link)
    replace(tmp_link, link)


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

    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Error taring up files')
        raise

    return archive
