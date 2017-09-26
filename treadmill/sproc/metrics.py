"""Treadmill metrics collector.

Collects Treadmill metrics and sends them to Graphite.
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import glob
import logging
import os
import time
import urllib

import click

from treadmill import appenv
from treadmill import exc
from treadmill import fs
from treadmill import restclient
from treadmill import rrdutils
from treadmill.metrics import rrd

#: Metric collection interval (every X seconds)
_METRIC_STEP_SEC_MIN = 15
_METRIC_STEP_SEC_MAX = 300


_LOGGER = logging.getLogger(__name__)

#            ( rrd file's basename,  cgroup name)
CORE_RRDS = {'apps': 'treadmill.apps.rrd',
             'core': 'treadmill.core.rrd',
             'treadmill': 'treadmill.system.rrd'}


def _sys_svcs(root_dir):
    """Contructs list of system services."""
    return sorted([
        os.path.basename(s)
        for s in glob.glob(os.path.join(root_dir, 'init', '*'))
        if not (s.endswith('.out') or s.endswith('.err'))])


def _update_core_rrds(data, core_metrics_dir, rrdclient, step, sys_maj_min):
    """Update core rrds"""
    interval = int(step) * 2
    total = 0

    for cgrp in data:
        rrd_basename = CORE_RRDS[cgrp]
        rrdfile = os.path.join(core_metrics_dir, rrd_basename)

        rrd.prepare(rrdclient, rrdfile, step, interval)
        if rrd.update(rrdclient, rrdfile, data[cgrp], sys_maj_min):
            total += 1

    return total


def _update_service_rrds(data, core_metrics_dir, rrdclient, step, sys_maj_min):
    """Update core services rrds"""
    interval = int(step) * 2
    total = 0

    for svc in data:
        rrdfile = os.path.join(core_metrics_dir, '{svc}.rrd'.format(svc=svc))

        rrd.prepare(rrdclient, rrdfile, step, interval)
        if rrd.update(rrdclient, rrdfile, data[svc], sys_maj_min):
            total += 1

    _LOGGER.debug(
        'Updated %d service metrics from maj:min %s',
        total, sys_maj_min
    )
    return total


def _update_app_rrds(data, app_metrics_dir, rrdclient, step, tm_env):
    """Update core services rrds"""
    interval = int(step) * 2
    total = 0

    for app_unique_name in data:
        try:
            localdisk = tm_env.svc_localdisk.get(app_unique_name)
            blkio_major_minor = '{major}:{minor}'.format(
                major=localdisk['dev_major'],
                minor=localdisk['dev_minor'],
            )
        except (exc.TreadmillError, IOError, OSError):
            blkio_major_minor = None

        rrdfile = os.path.join(
            app_metrics_dir, '{app}.rrd'.format(app=app_unique_name))

        _LOGGER.debug(
            'Update %s metrics from maj:min %s',
            app_unique_name, blkio_major_minor)

        rrd.prepare(rrdclient, rrdfile, step, interval)
        if rrd.update(
                rrdclient, rrdfile, data[app_unique_name], blkio_major_minor):
            total += 1

    _LOGGER.debug('Updated %d container metrics', total)
    return total


def init():
    """Top level command handler."""

    # TODO: main is too long (R0915) and has too many branches (R0912),
    #       need to be refactored.
    #
    # pylint: disable=R0915,R0912
    @click.command()
    @click.option('--step', '-s',
                  type=click.IntRange(_METRIC_STEP_SEC_MIN,
                                      _METRIC_STEP_SEC_MAX),
                  default=_METRIC_STEP_SEC_MIN,
                  help='Metrics collection frequency (sec)')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--socket', help='unix-socket of cgroup API service',
                  required=True)
    def metrics(step, approot, socket):
        """Collect node and container metrics."""
        # CAUTION: urllib.quote_plus only works for Python2,
        # need to use urllib.parse.quote_plus in Python3
        remote = 'http+unix://{}'.format(urllib.quote_plus(socket))
        _LOGGER.info('remote cgroup API address %s', remote)

        tm_env = appenv.AppEnvironment(root=approot)

        app_metrics_dir = os.path.join(tm_env.metrics_dir, 'apps')
        core_metrics_dir = os.path.join(tm_env.metrics_dir, 'core')
        fs.mkdir_safe(app_metrics_dir)
        fs.mkdir_safe(core_metrics_dir)

        rrdclient = rrdutils.RRDClient('/tmp/treadmill.rrd')

        # Initiate the list for monitored applications
        monitored_apps = set(
            os.path.basename(metric_name)[:-len('.rrd')]
            for metric_name in glob.glob('%s/*' % app_metrics_dir)
            if metric_name.endswith('.rrd')
        )

        sys_maj_min = '{}:{}'.format(*fs.path_to_maj_min(approot))
        _LOGGER.info('Device sys maj:min = %s for approot: %s',
                     sys_maj_min, approot)

        second_used = 0
        while True:
            if step > second_used:
                time.sleep(step - second_used)

            starttime_sec = time.time()
            count = 0
            data = restclient.get(remote, '/cgroup/_bulk', auth=None).json()

            count += _update_core_rrds(
                data['treadmill'], core_metrics_dir, rrdclient,
                step, sys_maj_min
            )

            count += _update_service_rrds(
                data['core'], core_metrics_dir, rrdclient, step, sys_maj_min
            )

            count += _update_app_rrds(
                data['app'], app_metrics_dir, rrdclient, step, tm_env
            )

            # Removed metrics for apps that are not present anymore
            seen_apps = set(data['app'].keys())
            for app_unique_name in monitored_apps - seen_apps:
                rrdfile = os.path.join(
                    app_metrics_dir, '{app}.rrd'.format(app=app_unique_name))
                _LOGGER.info('removing %r', rrdfile)
                rrd.finish(rrdclient, rrdfile)

            monitored_apps = seen_apps

            second_used = time.time() - starttime_sec
            _LOGGER.info('Got %d cgroups metrics in %.3f seconds',
                         count, second_used)

        # Gracefull shutdown.
        _LOGGER.info('service shutdown.')

    return metrics
