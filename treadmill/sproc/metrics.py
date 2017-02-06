"""Treadmill metrics collector.

Collects Treadmill metrics and sends them to Graphite.
"""


import glob
import logging
import os
import time

import click

from treadmill import appmgr
from treadmill import exc
from treadmill import fs
from treadmill import rrdutils

#: Metric collection interval (every X seconds)
_METRIC_TIMEOUT_SEC = 60 * 2
_METRIC_TIMEOUT_SEC = 10


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
    @click.option('--step', '-s', type=int, default=_METRIC_TIMEOUT_SEC,
                  help='Metrics collection frequency (sec)')
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    def metrics(step, approot):
        """Collect node and container metrics."""
        app_env = appmgr.AppEnvironment(root=approot)

        app_metrics_dir = os.path.join(app_env.metrics_dir, 'apps')
        core_metrics_dir = os.path.join(app_env.metrics_dir, 'core')
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

        sys_maj_min = '%s:0' % os.major(os.stat(approot).st_dev)
        _LOGGER.info('Device maj:min = %s for approot: %s', sys_maj_min,
                     approot)

        core_rrds = ['treadmill.apps.rrd',
                     'treadmill.core.rrd',
                     'treadmill.system.rrd']

        for core_rrd in core_rrds:
            rrdfile = os.path.join(core_metrics_dir, core_rrd)
            if not os.path.exists(rrdfile):
                rrdclient.create(rrdfile, step, interval)

        while True:
            rrdclient.update(
                os.path.join(core_metrics_dir, 'treadmill.apps.rrd'),
                rrdutils.app_metrics('treadmill/apps', sys_maj_min))
            rrdclient.update(
                os.path.join(core_metrics_dir, 'treadmill.core.rrd'),
                rrdutils.app_metrics('treadmill/core', sys_maj_min))
            rrdclient.update(
                os.path.join(core_metrics_dir, 'treadmill.system.rrd'),
                rrdutils.app_metrics('treadmill/system', sys_maj_min))

            for svc in sys_svcs:
                if svc in sys_svcs_no_metrics:
                    continue

                rrdfile = os.path.join(core_metrics_dir,
                                       '{svc}.rrd'.format(svc=svc))
                if not os.path.exists(rrdfile):
                    rrdclient.create(rrdfile, step, interval)

                svc_cgrp = os.path.join('treadmill', 'core', svc)
                svc_metrics = rrdutils.app_metrics(svc_cgrp, sys_maj_min)
                rrdclient.update(rrdfile, svc_metrics)

            seen_apps = set()
            for app_dir in glob.glob('%s/*' % app_env.apps_dir):
                if not os.path.isdir(app_dir):
                    continue

                app_unique_name = os.path.basename(app_dir)
                seen_apps.add(app_unique_name)
                try:
                    localdisk = app_env.svc_localdisk.get(app_unique_name)
                    blkio_major_minor = '{major}:{minor}'.format(
                        major=localdisk['dev_major'],
                        minor=localdisk['dev_minor'],
                    )
                except (exc.TreadmillError, IOError, OSError):
                    blkio_major_minor = None

                rrd_file = os.path.join(
                    app_metrics_dir, '{app}.rrd'.format(app=app_unique_name))

                if not os.path.exists(rrd_file):
                    rrdclient.create(rrd_file, step, interval)

                app_cgrp = os.path.join('treadmill', 'apps', app_unique_name)
                app_metrics = rrdutils.app_metrics(app_cgrp, blkio_major_minor)
                rrdclient.update(rrd_file, app_metrics)

            for app_unique_name in monitored_apps - seen_apps:
                # Removed metrics for apps that are not present anymore
                rrd_file = os.path.join(
                    app_metrics_dir, '{app}.rrd'.format(app=app_unique_name))
                _LOGGER.info('removing %r', rrd_file)
                rrdclient.forget(rrd_file)
                os.unlink(rrd_file)

            monitored_apps = seen_apps
            time.sleep(step)

        # Gracefull shutdown.
        _LOGGER.info('service shutdown.')

    return metrics
