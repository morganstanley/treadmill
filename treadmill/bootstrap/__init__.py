"""Treadmill bootstrap module."""
from __future__ import absolute_import

import os
import errno
import logging
import tempfile
import importlib
import pkgutil
import stat
import six

import pkg_resources
import jinja2

from treadmill import fs

# This is required so that symlink API (os.symlink and other link related)
# work properly on windows.
if os.name == 'nt':
    import treadmill.syscall.winsymlink
    treadmill.syscall.winsymlink


__path__ = pkgutil.extend_path(__path__, __name__)

_LOGGER = logging.getLogger(__name__)

if os.name == 'nt':
    DEFAULT_INSTALL_DIR = 'c:\\'
    PLATFORM = 'windows'
else:
    DEFAULT_INSTALL_DIR = '/var/tmp'
    PLATFORM = 'linux'


def _update_stat(src_file, tgt_file):
    """chmod target file to match the source file."""
    src_stat = os.stat(src_file)
    tgt_stat = os.stat(tgt_file)

    if src_stat.st_mode != tgt_stat.st_mode:
        _LOGGER.debug('chmod %s %s', tgt_file, src_stat.st_mode)
        os.chmod(tgt_file, src_stat.st_mode)


def _is_executable(filename):
    """Check if file is executable."""
    if os.path.basename(filename) in ['run', 'finish', 'app_start']:
        return True

    if filename.endswith('.sh'):
        return True

    return False


def _rename_file(src, dst):
    """Rename the specified file"""

    if os.name == 'nt':
        # TODO: check that fs.rm_safe works on windows, and if not, fix
        #       fs.rm_safe.
        fs.rm_safe(dst)
    os.rename(src, dst)
    mode = os.stat(dst).st_mode
    mode |= (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    if _is_executable(dst):
        mode |= (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.chmod(dst, mode)


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
        tmp_file.write(content.encode('utf-8'))

    _rename_file(tmp_file.name, filename)


def _render(value, params):
    """Renders text, interpolating params."""
    return str(jinja2.Template(value).render(params))


def _install(package, src_dir, dst_dir, params, prefix_len=None, rec=None):
    """Interpolate source directory into target directory with params."""

    contents = pkg_resources.resource_listdir(package, src_dir)

    if prefix_len is None:
        prefix_len = len(src_dir) + 1

    for item in contents:
        resource_path = '/'.join([src_dir, item])
        dst_path = os.path.join(dst_dir, resource_path[prefix_len:])
        if pkg_resources.resource_isdir(package, '/'.join([src_dir, item])):
            fs.mkdir_safe(dst_path)
            if rec:
                rec.write('%s/\n' % dst_path)
            _install(package,
                     os.path.join(src_dir, item),
                     dst_dir,
                     params,
                     prefix_len=prefix_len,
                     rec=rec)
        else:
            if resource_path.endswith('.swp'):
                continue

            _LOGGER.info('Render: %s => %s', resource_path, dst_path)
            resource_str = pkg_resources.resource_string(package,
                                                         resource_path)
            if rec:
                rec.write('%s\n' % dst_path)
            _update(dst_path, _render(resource_str.decode('utf-8'), params))


def _interpolate_dict(value, params):
    """Recursively interpolate each value in parameters."""
    result = {}
    target = dict(value)
    counter = 0
    while counter < 100:
        counter += 1
        result = {k: _interpolate(v, params) for k, v in
                  six.iteritems(target)}
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


def install(package, dst_dir, params, run=None):
    """Installs the services."""
    fullname = '.'.join([__name__, package])

    module = importlib.import_module(fullname)
    defaults = {}
    defaults.update(getattr(module, 'DEFAULTS', {}))

    aliases = {}
    aliases.update(getattr(module, 'ALIASES', {}))

    aliases_path = [fullname]

    for _loader, name, _ in pkgutil.iter_modules(module.__path__):
        extension = '.'.join([fullname, name])
        extension_module = importlib.import_module(extension)
        defaults.update(getattr(extension_module, 'DEFAULTS', {}))
        aliases.update(getattr(extension_module, 'ALIASES', {}))
        aliases_path.append(extension)

    # TODO: this is ugly, error prone and should go away.
    #       aliases should be in default scope, everything else in _args.
    defaults['_alias'] = aliases
    defaults.update(aliases)
    defaults.update(params)

    defaults['aliases_path'] = ':'.join(aliases_path)

    interpolated = _interpolate(defaults, defaults)

    fs.mkdir_safe(dst_dir)
    with open(os.path.join(dst_dir, '.install'), 'w+') as rec:

        _install(fullname, PLATFORM, dst_dir, interpolated, rec=rec)

        for _loader, name, _ in pkgutil.iter_modules(module.__path__):
            extension = '.'.join([fullname, name])
            extension_module = importlib.import_module(extension)
            _install(
                extension,
                '.'.join([name, PLATFORM]), dst_dir, interpolated,
                rec=rec
            )

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
