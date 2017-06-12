"""Treadmill metrics collector.

Collects Treadmill metrics and sends them to Graphite.
"""

from __future__ import absolute_import

import glob
import logging
import os
import time

import click

from treadmill import appenv
from treadmill import exc
from treadmill import fs
from treadmill import rrdutils
from treadmill.metrics import rrd

#: Metric collection interval (every X seconds)
_METRIC_STEP_SEC_MIN = 15
_METRIC_STEP_SEC_MAX = 300


_LOGGER = logging.getLogger(__name__)


def _core_svcs(root_dir):
    """Contructs list of core services."""
    return sorted([
        os.path.basename(s)
        for s in glob.glob(os.path.join(root_dir, 'init', '*'))
        if not (s.endswith('.out') or s.endswith('.err'))])


def init():
    """Top level command handler."""

    # TODO: main is too long, need to be refactored.
    #
    # pylint: disable=R0915
    @click.command()
    @click.option('--step', '-s',
                  type=click.IntRange(_METRIC_STEP_SEC_MIN,
                                      _METRIC_STEP_SEC_MAX),
                  default=_METRIC_STEP_SEC_MIN,
                  help='Metrics collection frequency (sec)')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    def metrics(step, approot):
        """Collect node and container metrics."""
        tm_env = appenv.AppEnvironment(root=approot)

        app_metrics_dir = os.path.join(tm_env.metrics_dir, 'apps')
        core_metrics_dir = os.path.join(tm_env.metrics_dir, 'core')
        fs.mkdir_safe(app_metrics_dir)
        fs.mkdir_safe(core_metrics_dir)

        interval = int(step) * 2

        rrdclient = rrdutils.RRDClient('/tmp/treadmill.rrd')

        # Initiate the list for monitored applications
        monitored_apps = set(
            os.path.basename(metric_name)[:-len('.rrd')]
            for metric_name in glob.glob('%s/*' % app_metrics_dir)
            if metric_name.endswith('.rrd')
        )

        sys_svcs = _core_svcs(approot)
        sys_svcs_no_metrics = set()

        sys_maj_min = '{}:{}'.format(*fs.path_to_maj_min(approot))
        sys_block_dev = fs.maj_min_to_blk(*fs.path_to_maj_min(approot))

        _LOGGER.info('Device %s maj:min = %s for approot: %s', sys_block_dev,
                     sys_maj_min, approot)

        core_rrds = ['treadmill.apps.rrd',
                     'treadmill.core.rrd',
                     'treadmill.system.rrd']

        for core_rrd in core_rrds:
            rrdfile = os.path.join(core_metrics_dir, core_rrd)
            if not os.path.exists(rrdfile):
                rrdclient.create(rrdfile, step, interval)

        while True:
            starttime_sec = time.time()
            rrd.update(
                rrdclient,
                os.path.join(core_metrics_dir, 'treadmill.apps.rrd'),
                'treadmill/apps', sys_maj_min, sys_block_dev
            )
            rrd.update(
                rrdclient,
                os.path.join(core_metrics_dir, 'treadmill.core.rrd'),
                'treadmill/core', sys_maj_min, sys_block_dev
            )
            rrd.update(
                rrdclient,
                os.path.join(core_metrics_dir, 'treadmill.system.rrd'),
                'treadmill', sys_maj_min, sys_block_dev
            )
            count = 3

            for svc in sys_svcs:
                if svc in sys_svcs_no_metrics:
                    continue

                rrdfile = os.path.join(core_metrics_dir,
                                       '{svc}.rrd'.format(svc=svc))
                if not os.path.exists(rrdfile):
                    rrdclient.create(rrdfile, step, interval)

                svc_cgrp = os.path.join('treadmill', 'core', svc)
                rrd.update(rrdclient, rrdfile, svc_cgrp, sys_maj_min,
                           sys_block_dev)
                count += 1

            seen_apps = set()
            for app_dir in glob.glob('%s/*' % tm_env.apps_dir):
                if not os.path.isdir(app_dir):
                    continue

                app_unique_name = os.path.basename(app_dir)
                seen_apps.add(app_unique_name)
                try:
                    localdisk = tm_env.svc_localdisk.get(app_unique_name)
                    blkio_major_minor = '{major}:{minor}'.format(
                        major=localdisk['dev_major'],
                        minor=localdisk['dev_minor'],
                    )
                    block_dev = localdisk['block_dev']
                except (exc.TreadmillError, IOError, OSError):
                    blkio_major_minor = None
                    block_dev = None

                rrd_file = os.path.join(
                    app_metrics_dir, '{app}.rrd'.format(app=app_unique_name))

                if not os.path.exists(rrd_file):
                    rrdclient.create(rrd_file, step, interval)

                app_cgrp = os.path.join('treadmill', 'apps', app_unique_name)
                rrd.update(rrdclient, rrd_file, app_cgrp, blkio_major_minor,
                           block_dev)
                count += 1

            for app_unique_name in monitored_apps - seen_apps:
                # Removed metrics for apps that are not present anymore
                rrd_file = os.path.join(
                    app_metrics_dir, '{app}.rrd'.format(app=app_unique_name))
                _LOGGER.info('removing %r', rrd_file)
                rrdclient.forget(rrd_file)
                os.unlink(rrd_file)

            monitored_apps = seen_apps

            second_used = time.time() - starttime_sec
            _LOGGER.info('Got %d cgroups metrics in %.3f seconds',
                         count, second_used)
            if step > second_used:
                time.sleep(step - second_used)

        # Gracefull shutdown.
        _LOGGER.info('service shutdown.')

    return metrics
