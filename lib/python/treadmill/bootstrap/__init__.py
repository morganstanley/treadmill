"""Treadmill bootstrap module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import io
import json
import logging
import os
import sys
import tempfile

if os.name == 'posix':
    import stat

import jinja2
import pkg_resources
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import fs
from treadmill import plugin_manager
from treadmill import supervisor
from treadmill import utils
from treadmill import yamlwrapper as yaml
from treadmill import subproc
from treadmill import logging as tm_logging

_LOGGER = logging.getLogger(__name__)

if os.name == 'nt':
    DEFAULT_INSTALL_DIR = 'c:\\'
    PLATFORM = 'windows'
else:
    DEFAULT_INSTALL_DIR = '/var/lib'
    PLATFORM = 'linux'

_CONTROL_DIR_NAME = supervisor.ScanDir.control_dir_name()
_CONTROL_DIR_FILE = '{}.yml'.format(_CONTROL_DIR_NAME)


def _is_executable(filename):
    """Check if file is executable.
    """
    # XXX: This is an ugly hack until we can replace bootstrap with
    #      a treadmill.supervisor based installation.
    if os.path.basename(filename) in ['run', 'finish', 'app_start',
                                      'SIGTERM', 'SIGHUP', 'SIGQUIT',
                                      'SIGINT', 'SIGUSR1', 'SIGUSR2']:
        return True

    if filename.endswith('.sh'):
        return True

    return False


def _is_scan_dir(package, src_dir, dst_dir):
    """Check if working on a scan dir.
    """
    if os.path.exists(os.path.join(dst_dir, _CONTROL_DIR_NAME)):
        return True

    package_name = package.__name__
    if pkg_resources.resource_isdir(package_name,
                                    os.path.join(src_dir, _CONTROL_DIR_NAME)):
        return True

    if pkg_resources.resource_exists(package_name,
                                     os.path.join(src_dir, _CONTROL_DIR_FILE)):
        return True

    return False


def _rename_file(src, dst):
    """Rename the specified file.
    """

    fs.replace(src, dst)
    if os.name == 'posix':
        mode = os.stat(dst).st_mode
        mode |= (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        if _is_executable(dst):
            mode |= (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.chmod(dst, mode)


def _update(filename, content):
    """Updates file with content if different.
    """
    try:
        with io.open(filename) as f:
            current = f.read()
            if current == content:
                return

    except OSError as os_err:
        if os_err.errno != errno.ENOENT:
            raise

    except IOError as io_err:  # pylint: disable=duplicate-except
        if io_err.errno != errno.ENOENT:
            raise

    with tempfile.NamedTemporaryFile(dir=os.path.dirname(filename),
                                     mode='w',
                                     prefix='.tmp',
                                     delete=False) as tmp_file:
        tmp_file.write(content)

    _rename_file(tmp_file.name, filename)


def _render(value, params):
    """Renders text, interpolating params.
    """
    return str(jinja2.Template(value).render(params))


def _interpolate_service_conf(resource_path, service_conf, name, params):
    """Interpolates the service config.
    """
    params['name'] = name
    new_service_conf = {'name': name}

    if 'command' not in service_conf:
        raise Exception(
            'Service def did not include command: %s' % resource_path
        )

    new_service_conf['command'] = _interpolate_scalar(
        service_conf.get('command'), params)

    monitor_policy = service_conf.get('monitor_policy', None)
    if monitor_policy is not None:
        monitor_policy = _interpolate_dict(monitor_policy, params)
        if 'tombstone' not in monitor_policy or \
                'path' not in monitor_policy['tombstone']:
            raise Exception(
                'Service def ombstone path missing: %s' % resource_path
            )

        tombstone_path = monitor_policy['tombstone']['path']
        tombstone_path = _interpolate_scalar(tombstone_path, params)

        tombstone_id = monitor_policy['tombstone'].get('id', name)
        tombstone_id = _interpolate_scalar(tombstone_id, params)

        new_policy = {
            'limit': int(monitor_policy.get('limit', 0)),
            'interval': int(monitor_policy.get('interval', 60)),
            'tombstone': {
                'uds': False,
                'path': tombstone_path,
                'id': tombstone_id,
                'no_exit_info': monitor_policy['tombstone'].get('no_exit_info',
                                                                False)
            }
        }

        monitor_policy = new_policy

    new_service_conf['monitor_policy'] = monitor_policy
    new_service_conf['userid'] = _interpolate_scalar(
        service_conf.get('user', 'root'), params)
    new_service_conf['downed'] = service_conf.get('downed', False)
    new_service_conf['environ_dir'] = _interpolate_scalar(
        service_conf.get('environ_dir', None), params)
    new_service_conf['environ'] = _interpolate(
        service_conf.get('environ', None), params)
    new_service_conf['notification_fd'] = service_conf.get(
        'notification_fd', None)
    new_service_conf['call_before_run'] = _interpolate(service_conf.get(
        'call_before_run', None), params)
    new_service_conf['call_before_finish'] = _interpolate(service_conf.get(
        'call_before_finish', None), params)
    new_service_conf['logger_args'] = service_conf.get('logger_args', None)

    files = []
    data_dir = service_conf.get('data_dir', None)
    if data_dir is not None:
        for item in utils.get_iterable(data_dir):
            if 'path' not in item:
                continue

            file = {
                'path': item['path']
            }

            content = ''
            if 'content' in item:
                content = _interpolate_scalar(item['content'], params)

            file['content'] = content
            file['executable'] = item.get('executable', False)

            files.append(file)

    new_service_conf['data_dir'] = files

    del params['name']

    _LOGGER.debug('Service config for %s: %r', name, new_service_conf)
    return new_service_conf


def _install_services(scan_dir, package, src_dir, dst_dir, params, prefix_len,
                      rec=None):
    """Expand services in scan directory and install.
    """
    package_name = package.__name__
    contents = pkg_resources.resource_listdir(package_name, src_dir)

    for item in contents:
        if item in (_CONTROL_DIR_NAME, _CONTROL_DIR_FILE):
            continue

        resource_path = os.path.join(src_dir, item)
        if pkg_resources.resource_isdir(package_name,
                                        os.path.join(src_dir, item)):
            dst_path = os.path.join(dst_dir, resource_path[prefix_len:])

            fs.mkdir_safe(dst_path)
            if rec:
                rec.write('%s\n' % os.path.join(dst_path, ''))

            _install(
                package,
                os.path.join(src_dir, item),
                dst_dir,
                params,
                prefix_len=prefix_len,
                rec=rec
            )
        elif resource_path.endswith('.yml'):
            dst_path = os.path.join(dst_dir, resource_path[prefix_len:-4])
            name = os.path.basename(dst_path)

            _LOGGER.info('Expand service (%s): %s => %s', name, resource_path,
                         dst_path)

            fs.mkdir_safe(dst_path)
            if rec:
                rec.write('%s\n' % os.path.join(dst_path, ''))

            service_conf_file = pkg_resources.resource_string(
                package_name,
                resource_path
            )

            if not service_conf_file:
                _LOGGER.warning('Service def was empty: %s', resource_path)
                continue

            service_conf = yaml.load(service_conf_file.decode('utf8'))
            service_conf = _interpolate_service_conf(
                resource_path, service_conf, name, params)

            svc = supervisor.create_service(
                scan_dir,
                service_conf['name'],
                service_conf['command'],
                userid=service_conf['userid'],
                downed=service_conf['downed'],
                environ_dir=service_conf['environ_dir'],
                environ=service_conf['environ'],
                monitor_policy=service_conf['monitor_policy'],
                notification_fd=service_conf['notification_fd'],
                call_before_run=service_conf['call_before_run'],
                call_before_finish=service_conf['call_before_finish'],
                logger_args=service_conf['logger_args'],
                ionice_prio=0,
            )

            for file in service_conf['data_dir']:
                permission = 0o644
                if file['executable']:
                    permission = 0o755
                fs.write_safe(
                    os.path.join(svc.data_dir, file['path']),
                    lambda f, file=file: f.write(
                        file['content']
                    ),
                    mode='w',
                    permission=permission
                )


def _install_scan_dir(package, src_dir, dst_dir, params, prefix_len, rec=None):
    """Interpolate source directory as a scan directory containing service
    definitions.
    """
    package_name = package.__name__

    src_control_dir = os.path.join(src_dir, _CONTROL_DIR_NAME)
    src_control_dir_file = os.path.join(src_dir, _CONTROL_DIR_FILE)
    dst_path = os.path.join(dst_dir, src_dir[prefix_len:])
    dst_control_dir = os.path.join(dst_path, _CONTROL_DIR_NAME)
    scan_dir = None

    if not os.path.exists(dst_control_dir):
        fs.mkdir_safe(dst_control_dir)
        if rec:
            rec.write('%s\n' % os.path.join(dst_control_dir, ''))

    if pkg_resources.resource_isdir(package_name, src_control_dir):
        _install(package, src_control_dir, dst_dir, params,
                 prefix_len=prefix_len, rec=rec)

    elif pkg_resources.resource_exists(package_name, src_control_dir_file):
        _LOGGER.info('Expand control dir: %s => %s', src_control_dir_file,
                     dst_control_dir)

        svscan_conf_file = pkg_resources.resource_string(
            package_name,
            src_control_dir_file
        )

        if svscan_conf_file:
            svscan_conf = yaml.load(svscan_conf_file.decode('utf8'))
        else:
            svscan_conf = {}

        scan_dir = supervisor.create_scan_dir(
            dst_path,
            svscan_conf.get('finish_timeout', 0),
            wait_cgroups=svscan_conf.get('wait_cgroups', None),
            kill_svc=svscan_conf.get('kill_svc', None)
        )
        scan_dir.write()

    if not scan_dir:
        scan_dir = supervisor.ScanDir(dst_path)

    _install_services(
        scan_dir,
        package,
        src_dir,
        dst_dir,
        params,
        prefix_len=prefix_len,
        rec=rec
    )


def _install(package, src_dir, dst_dir, params, prefix_len=None, rec=None):
    """Interpolate source directory into target directory with params.
    """
    package_name = package.__name__
    _LOGGER.info(
        'Installing package: %s %s %s', package_name, src_dir, dst_dir
    )

    contents = pkg_resources.resource_listdir(package_name, src_dir)

    if prefix_len is None:
        prefix_len = len(src_dir) + 1

    for item in contents:
        resource_path = os.path.join(src_dir, item)
        dst_path = os.path.join(dst_dir, resource_path[prefix_len:])
        if pkg_resources.resource_isdir(package_name,
                                        os.path.join(src_dir, item)):
            fs.mkdir_safe(dst_path)

            # Check directory ownership.
            owner_rsrc = os.path.join(resource_path, '.owner')
            if pkg_resources.resource_exists(package_name, owner_rsrc):
                owner = _interpolate(
                    pkg_resources.resource_string(
                        package_name, owner_rsrc
                    ).decode(),
                    params
                ).strip()

                try:
                    _LOGGER.info('Setting owner: %r - %r', dst_path, owner)
                    (uid, gid) = utils.get_uid_gid(owner)
                    os.chown(dst_path, uid, gid)
                except (IOError, OSError) as err:
                    if err.errno != errno.ENOENT:
                        raise

            if rec:
                rec.write('%s\n' % os.path.join(dst_path, ''))

            install_fn = _install

            # Test if is a scan dir first
            if _is_scan_dir(package, os.path.join(src_dir, item), dst_path):
                _LOGGER.info('Scan dir found: %s => %s', resource_path,
                             dst_path)
                install_fn = _install_scan_dir

            install_fn(
                package,
                os.path.join(src_dir, item),
                dst_dir,
                params,
                prefix_len=prefix_len,
                rec=rec
            )
        else:
            if resource_path.endswith('.swp'):
                continue
            if resource_path.endswith('.owner'):
                continue

            resource_str = pkg_resources.resource_string(
                package_name,
                resource_path
            )

            if rec:
                rec.write('%s\n' % dst_path)
            _update(dst_path, _render(resource_str.decode('utf8'), params))


def _interpolate_dict(value, params):
    """Recursively interpolate each value in parameters.
    """
    result = {}
    target = dict(value)
    counter = 0
    while counter < 100:
        counter += 1
        result = {
            k: _interpolate(v, params)
            for k, v in six.iteritems(target)
        }
        if result == target:
            break
        target = dict(result)
    else:
        raise Exception('Too many recursions: %s %s' % (value, params))

    return result


def _interpolate_list(value, params):
    """Interpolate each of the list element.
    """
    return [_interpolate(member, params) for member in value]


def _interpolate_scalar(value, params):
    """Interpolate string value by rendering the template.
    """
    if isinstance(value, six.string_types):
        return _render(value, params)
    else:
        # Do not interpolate numbers.
        return value


def _interpolate(value, params=None):
    """Interpolate the value, switching by the value type.
    """
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
    """Runs the services.
    """
    if os.name == 'nt':
        sys.exit(subprocess.call(script))
    else:
        utils.sane_execvp(script, [script])


def install(package, dst_dir, params, run=None, profile=None):
    """Installs the services.
    """
    _LOGGER.info('install: %s - %s, profile: %s', package, dst_dir, profile)

    packages = [package]

    module = plugin_manager.load('treadmill.bootstrap', package)
    extension_module = None
    if profile:
        _LOGGER.info('Installing profile: %s', profile)
        extension_name = '{}.{}'.format(package, profile)
        packages.append(extension_name)

        try:
            extension_module = plugin_manager.load('treadmill.bootstrap',
                                                   extension_name)
        except KeyError:
            _LOGGER.info('Extension not defined: %s, profile: %s',
                         package, profile)

    subproc.load_packages(packages, lazy=False)

    # Store resolved aliases
    aliases_path = os.path.join(dst_dir, '.aliases.json')
    aliases = subproc.get_aliases()
    with io.open(aliases_path, 'w') as f_aliases:
        f_aliases.write(json.dumps(aliases))

    defaults = {}
    defaults.update(getattr(module, 'DEFAULTS', {}))

    if extension_module:
        defaults.update(getattr(extension_module, 'DEFAULTS', {}))

    # TODO: this is ugly, error prone and should go away.
    #       aliases should be in default scope, everything else in _args.
    defaults['_alias'] = aliases
    defaults.update(aliases)
    defaults.update(params)

    defaults['aliases_path'] = aliases_path
    os.environ['TREADMILL_ALIASES_PATH'] = defaults['aliases_path']

    interpolated = _interpolate(defaults, defaults)

    fs.mkdir_safe(dst_dir)
    with io.open(os.path.join(dst_dir, '.install'), 'w') as rec:

        _install(module, PLATFORM, dst_dir, interpolated, rec=rec)

        if extension_module:
            _install(
                extension_module,
                '.'.join([profile, PLATFORM]), dst_dir, interpolated,
                rec=rec
            )

    # Extract logging configuration.
    logconf_dir = os.path.join(dst_dir, 'logging')
    fs.mkdir_safe(logconf_dir)
    tm_logging.write_configs(logconf_dir)

    # Write entry-point cache
    distributions = pkg_resources.AvailableDistributions()

    plugin_manager.dump_cache(
        os.path.join(dst_dir, 'plugins.json'), distributions
    )

    if run:
        _run(run)


def interpolate(value, params=None):
    """Interpolate value.
    """
    return _interpolate(value, params)


def wipe(wipe_me, wipe_script):
    """Check if flag file is present, invoke cleanup script.
    """
    if os.path.exists(wipe_me):
        _LOGGER.info('Requested clean start, calling: %s', wipe_script)
        subprocess.check_call(wipe_script)
    else:
        _LOGGER.info('Preserving data, no clean restart.')
