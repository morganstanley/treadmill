"""Treadmill bootstrap module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import jinja2
import six

from treadmill import utils

_LOGGER = logging.getLogger(__name__)


def render(value, params):
    """Renders text, interpolating params.
    """
    return str(jinja2.Template(value).render(params))


def interpolate_service_conf(resource_path, service_conf, name, params):
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
        return render(value, params)
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


def interpolate(value, params=None):
    """Interpolate value.
    """
    return _interpolate(value, params)


__all__ = ['interpolate', 'interpolate_service_conf', 'render']
