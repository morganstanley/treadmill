"""module to forward metrics to watchtower
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import time

import six

from treadmill import context
from treadmill import restclient
from treadmill import sysinfo

from treadmill.ms.watchtower import api as wtapi

FACET = 'CONTAINER'

_LOGGER = logging.getLogger(__name__)


# cgroup metrics key => watchtower metrics key map
def _parse_blkio_value(key_tpl):
    """Parse and generate blkio value for watchtower
    """
    def _inner(value):
        return [
            (key_tpl.format(maj_min), data)
            for (maj_min, data) in value.items()
        ]

    return _inner


def _parse_blkio_rw_data(key_tpl, short_name=False):
    """Parse and generate blkio read write data for watchtower
    """
    read_name = 'r' if short_name else 'read'
    write_name = 'w' if short_name else 'write'

    def _inner(value):
        results = []
        for (maj_min, data) in value.items():
            results.append(
                (key_tpl.format(read_name, maj_min), data.get('Read', 0))
            )
            results.append(
                (key_tpl.format(write_name, maj_min), data.get('Write', 0))
            )

        return results

    return _inner


_METRICS_MAP = {
    # cpu related
    'cpuacct.stat': lambda val: [
        ('system.cpu.util[,system,nanosec]', val.get('system', 0)),
        ('system.cpu.util[,user,nanosec]', val.get('user', 0))
    ],
    'cpu.stat': lambda val: [
        ('system.cpu.util[,nr_periods,count]',
         val.get('nr_periods', 0)),
        ('system.cpu.util[,nr_throttled,count]',
         val.get('nr_throttled', 0)),
        ('system.cpu.util[,throttled_time,nanose]',
         val.get('throttled_time', 0)),
    ],
    'cpu.shares': 'system.cpu.shares',
    'cpuacct.usage': 'system.cpu.util[,,nanosec]',
    'cpuacct.usage_percpu': lambda val: [
        ('system.cpu.util[{},,nanosec]'.format(idx), v)
        for idx, v in enumerate(val)
    ],
    # memory related
    'memory.limit_in_bytes': 'vm.memory.size[cgroup_total]',
    'memory.failcnt': 'vm.memory.size[cgroup_failed_count]',
    'memory.max_usage_in_bytes': 'vm.memory.size[cgroup_max_used]',
    'memory.soft_limit_in_bytes': 'vm.memory.size[cgroup_soft_limit]',
    'memory.usage_in_bytes': 'vm.memory.size[cgroup_used]',
    'memory.memsw.failcnt': 'vm.memory.size[memory_swap_failed_count]',
    'memory.memsw.limit_in_bytes': 'vm.memory.size[memory_swap_total]',
    'memory.memsw.max_usage_in_bytes': 'vm.memory.size[memory_swap_max_used]',
    'memory.memsw.usage_in_bytes': 'vm.memory.size[memory_swap_used]',
    'memory.stat': lambda val: [
        # take all total_xxx values
        ('vm.memory.size[{}]'.format(key), val[key])
        for key in val.keys() if key.startswith('total_')
    ],
    # blkio
    'blkio.io_merged': _parse_blkio_rw_data(
        'ios.blkio[merged,{},{},count'
    ),
    'blkio.io_queued': _parse_blkio_rw_data(
        'ios.blkio[queued,{},{},count]'
    ),
    'blkio.io_service_bytes': _parse_blkio_rw_data(
        'ios.{}bytes[{},cfq_scheduler]', short_name=True
    ),
    'blkio.io_serviced': _parse_blkio_rw_data(
        'ios.{}ops[{},cfq_scheduler]', short_name=True
    ),
    'blkio.throttle.io_service_bytes': _parse_blkio_rw_data(
        'ios.{}bytes[{},]', short_name=True
    ),
    'blkio.throttle.io_serviced': _parse_blkio_rw_data(
        'ios.{}ops[{},]', short_name=True
    ),
    'blkio.sectors': _parse_blkio_value('ios.blkio[sectors,{},count]'),
    'blkio.time': _parse_blkio_value('ios.blkio[access_time,{},millisecond]'),
}


def _send_metrics_group(sender, data, instance):
    """Send all metrics in a cgroup
    """
    timestamp = data.pop('timestamp')

    for cgroup_key in data.keys():

        if cgroup_key not in _METRICS_MAP:
            _LOGGER.debug('unknown cgroup key %s', cgroup_key)
            continue

        mapper = _METRICS_MAP[cgroup_key]
        value = data[cgroup_key]

        if isinstance(mapper, six.string_types):
            sender.send(mapper, value, instance, timestamp)
        else:
            for (key, val) in mapper(value):
                sender.send(key, val, instance, timestamp)


def _send_service_metrics(sender, data):
    """Update core services metrics
    """
    count = 0
    # watchtower need
    treadmill_id = os.environ['TREADMILL_ID']
    hostname = sysinfo.hostname()

    for svc in data:
        _send_metrics_group(
            sender, data[svc], '{}.{}.{}'.format(treadmill_id, hostname, svc)
        )
        count += 1

    return count


def _send_app_metrics(sender, data):
    """Update container app metrics
    """
    count = 0
    for app_unique_name in data:
        _send_metrics_group(sender, data[app_unique_name], app_unique_name)
        count += 1
    return count


class MetricsForwarder(object):
    """Read data from cgroup info service, then forward to Watchtower collector
    it accept WT collector host:port and cgroup service address as parameters

    """
    def __init__(self, host, port, remote):
        cell = context.GLOBAL.cell
        self._sender = wtapi.MetricsSender(cell, FACET, host=host, port=port)
        self._remote = remote

    def run(self, step, with_service=False):
        """iterate to forward metrics to watchtower
        """
        second_used = 0
        while True:
            if step > second_used:
                time.sleep(step - second_used)
            self._sender.dispatch()

            starttime_sec = time.time()
            count = 0
            data = restclient.get(
                self._remote, '/cgroup/_bulk', auth=None
            ).json()

            count += _send_app_metrics(self._sender, data['app'])

            if with_service:
                count += _send_service_metrics(self._sender, data['core'])

            second_used = time.time() - starttime_sec
            _LOGGER.info('Added %d cgroups metrics in %.3f seconds',
                         count, second_used)
