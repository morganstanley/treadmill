"""Treadmill bootstrap module."""
from __future__ import absolute_import

import os
import errno
import logging
import tempfile

import jinja2

from treadmill import fs

# This is required so that symlink API (os.symlink and other link related)
# work properly on windows.
if os.name == 'nt':
    import treadmill.syscall.winsymlink  # pylint: disable=W0611


_LOGGER = logging.getLogger(__name__)

if os.name == 'nt':
    DEFAULT_INSTALL_DIR = 'c:\\'
else:
    DEFAULT_INSTALL_DIR = '/var/tmp'


def _update_stat(src_file, tgt_file):
    """chmod target file to match the source file."""
    src_stat = os.stat(src_file)
    tgt_stat = os.stat(tgt_file)

    if src_stat.st_mode != tgt_stat.st_mode:
        _LOGGER.debug('chmod %s %s', tgt_file, src_stat.st_mode)
        os.chmod(tgt_file, src_stat.st_mode)


def _rename_file(src, dst):
    """Rename the specified file"""

    if os.name == 'nt':
        # TODO: check that fs.rm_safe works on windows, and if not, fix
        #       fs.rm_safe.
        fs.rm_safe(dst)
    os.rename(src, dst)


def _update(filename, content):
    """Updates file with content if different."""
    _LOGGER.debug('Updating %s', filename)
    try:
        with open(filename) as f:
            current = f.read()
            if current == content:
                return

    except OSError as os_err:
        if os_err.errno != errno.ENOENT:
            raise
    except IOError as io_err:
        if io_err.errno != errno.ENOENT:
            raise

    with tempfile.NamedTemporaryFile(dir=os.path.dirname(filename),
                                     prefix='.tmp',
                                     delete=False) as tmp_file:
        tmp_file.write(content)

    _rename_file(tmp_file.name, filename)


def _render(value, params):
    """Renders text, interpolating params."""
    return str(jinja2.Template(value).render(params))


def _install(src_dir, dst_dir, params):
    """Interpolate source directory into target directory with params."""
    for root, _dirs, files in os.walk(src_dir):
        subdir = root.replace(src_dir, dst_dir)
        if not os.path.exists(subdir):
            fs.mkdir_safe(subdir)
        for filename in files:
            if filename == '.' or filename == '..':
                continue

            src_file = os.path.join(root, filename)
            tgt_file = os.path.join(subdir, filename)
            if os.path.islink(src_file):
                link = _render(os.readlink(src_file), params)
                os.symlink(link, tgt_file)
                if not os.path.exists(tgt_file):
                    _LOGGER.critical('Broken symlink: %s -> %s, %r',
                                     src_file, tgt_file, params)
                    raise Exception('Broken symlink, aborting install.')
            else:
                with open(src_file) as src:
                    _update(tgt_file, _render(src.read(), params))
                _update_stat(src_file, tgt_file)


def _interpolate_dict(value, params):
    """Recursively interpolate each value in parameters."""
    result = {}
    target = dict(value)
    counter = 0
    while counter < 100:
        counter += 1
        result = {k: _interpolate(v, params) for k, v in
                  target.iteritems()}
        if result == target:
            break
        target = dict(result)
    else:
        raise Exception('Too many recursions: %s %s', value, params)

    return result


def _interpolate_list(value, params):
    """Interpolate each of the list element."""
    return [_interpolate(member, params) for member in value]


def _interpolate_scalar(value, params):
    """Interpolate string value by rendering the template."""
    if isinstance(value, str):
        return _render(value, params)
    else:
        # Do not interpolate numbers.
        return value


def _interpolate(value, params=None):
    """Interpolate the value, switching by the value type."""
    if params is None:
        params = value

    try:
        if isinstance(value, list):
            return _interpolate_list(value, params)
        if isinstance(value, dict):
            return _interpolate_dict(value, params)
        return _interpolate_scalar(value, params)
    except Exception:
        _LOGGER.critical('error interpolating: %s %s', value, params)
        raise


def _run(script):
    """Runs the services."""
    os.execvp(script, [script])


def install(src_dir, dst_dir, params, run=None):
    """Installs the services."""
    _install(src_dir, dst_dir, _interpolate(params, params))
    if run:
        _run(os.path.join(dst_dir, run))


def interpolate(value, params=None):
    """Interpolate value."""
    return _interpolate(value, params)


def wipe(wipe_me, wipe_script):
    """Check if flag file is present, invoke cleanup script."""
    if os.path.exists(wipe_me):
        _LOGGER.info('Requested clean start, calling: %s', wipe_script)
        os.system(wipe_script)
    else:
        _LOGGER.info('Preserving data, no clean restart.')
