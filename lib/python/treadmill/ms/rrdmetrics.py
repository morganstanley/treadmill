"""All utilities to download rrd and generate metrics
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import codecs
import io
import logging
import os
import time

import pkg_resources
import six

from six.moves import urllib_parse

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import fs
from treadmill import restclient
from treadmill import rrdutils
from treadmill import utils


_LOGGER = logging.getLogger(__name__)


# TODO: this list should be discoverable from the server rather than
#                hardcoded. GET /metrics/core should return this list.
_SYSTEM_SERVICES = [
    # Total metrics for non-treadmill (system), core services and all apps.
    'treadmill.system',
    'treadmill.core',
    'treadmill.apps',
]


def _local_url(*name_parts):
    """Return the url with which the application metrics can be retrieved."""
    return '/local-app/{}'.format(urllib_parse.quote('/'.join(name_parts)))


def _metrics_url(*name_parts):
    """Return the url with which the application metrics can be retrieved."""
    return '/metrics/{}'.format(urllib_parse.quote('/'.join(name_parts)))


def _rrdfile(outdir, *fname_parts):
    """Return the full path of the rrd file where the metrics will be saved.
    """
    return os.path.join(outdir, '-'.join(fname_parts) + '.rrd')


def _get_app_rsrc(nodeinfo_url, local_url):
    """Return the application's reserved resources from the manifest."""
    _LOGGER.debug('Get reserved resources of the application')

    mf = restclient.get(nodeinfo_url, local_url).json()
    rsrc = {rsrc: mf[rsrc] for rsrc in ('cpu', 'disk', 'memory') if rsrc in mf}

    # local-app returns 'cpu' as an int.
    if '%' not in str(rsrc['cpu']):
        rsrc['cpu'] = '{}%'.format(rsrc['cpu'])

    return rsrc


def get_app_metrics(endpoint, app, timeframe, uniq='running', outdir=None):
    """Retreives app metrics."""

    api = 'http://{0}:{1}'.format(endpoint['host'], endpoint['port'])

    reserved_rsrc = _get_app_rsrc(api, _local_url(app, uniq))

    report_file = download_rrd(
        api, _metrics_url(app, uniq),
        _rrdfile(outdir, app, uniq), timeframe, outdir=outdir,
        reserved_rsrc=reserved_rsrc
    )
    return report_file


def get_server_metrics(endpoint, server, timeframe, services=None,
                       outdir=None):
    """Get core services metrics."""
    api = 'http://{0}:{1}'.format(endpoint['host'], endpoint['port'])

    if not services:
        services = _SYSTEM_SERVICES

    for svc in services:
        svc_outdir = os.path.join(outdir, svc)

        yield download_rrd(
            api, _metrics_url(svc), _rrdfile(svc_outdir, server, svc),
            timeframe, outdir=svc_outdir
        )


def download_rrd(nodeinfo_url, metrics_url, rrdfile, timeframe, outdir=None,
                 reserved_rsrc=None):
    """Get rrd file and store in output directory."""
    fs.mkdir_safe(outdir)

    _LOGGER.info('Download metrics from %s%s', nodeinfo_url, metrics_url)
    with restclient.get(nodeinfo_url, metrics_url, stream=True) as resp:
        with io.open(rrdfile, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=128 * 1024):
                f.write(chunk)

    return gen_report(
        rrdfile, timeframe, outdir, reserved_rsrc=reserved_rsrc
    )


def gen_report(rrdfile, timeframe, outdir=None, reserved_rsrc=None):
    """Generate a report from the content of the rrd file."""
    reserved_rsrc = reserved_rsrc or dict(cpu='0%', disk='0G')

    first_ts = rrdutils.first(rrdfile, timeframe, exec_on_node=False)
    last_ts = rrdutils.last(rrdfile, exec_on_node=False)
    from_ = time.strftime('%b/%d %R', time.gmtime(int(first_ts)))
    to = time.strftime('%b/%d %R%z', time.gmtime(int(last_ts)))

    diagrams = [
        [
            os.path.join(outdir, 'memory.svg'),
            '--title=Memory Usage [%s - %s]' % (from_, to), '--imgformat=SVG',
            '--start=%s' % first_ts, '--end=%s' % last_ts,
            '--vertical-label=bytes',
            'DEF:memory_usage=%s:memory_usage:MAX' % rrdfile,
            'LINE1:memory_usage#0000FF:memory usage',
            'DEF:memory_hardlimit=%s:memory_hardlimit:MAX' % rrdfile,
            'LINE1:memory_hardlimit#CC0000:memory limit'
        ], [
            os.path.join(outdir, 'cpu_usage.svg'),
            '--title=CPU Usage [%s - %s]' % (from_, to), '--imgformat=SVG',
            '--start=%s' % first_ts, '--end=%s' % last_ts,
            '--vertical-label=%',
            'DEF:cpu_usage=%s:cpu_usage:AVERAGE' % rrdfile,
            'LINE1:cpu_usage#0000FF:cpu usage',
            'HRULE:%s#CC0000:reservation of compute '
            '(%s)' % (reserved_rsrc['cpu'][:-1], reserved_rsrc['cpu']),
        ], [
            os.path.join(outdir, 'cpu_ratio.svg'),
            '--title=CPU Ratio [%s - %s]' % (from_, to), '--imgformat=SVG',
            '--start=%s' % first_ts, '--end=%s' % last_ts,
            'DEF:cpu_ratio=%s:cpu_ratio:AVERAGE' % rrdfile,
            'LINE1:cpu_ratio#0000FF:cpu ratio',
        ], [
            os.path.join(outdir, 'blk_iops.svg'),
            '--title=Block I/O [%s - %s]' % (from_, to), '--imgformat=SVG',
            '--start=%s' % first_ts, '--end=%s' % last_ts,
            '--vertical-label=operations/second',
            'DEF:blk_read_iops=%s:blk_read_iops:MAX' % rrdfile,
            'LINE1:blk_read_iops#0000FF:read iops',
            'DEF:blk_write_iops=%s:blk_write_iops:MAX' % rrdfile,
            'LINE1:blk_write_iops#CC0000:write iops'
        ], [
            os.path.join(outdir, 'blk_bps.svg'),
            '--title=Block I/O [%s - %s]' % (from_, to), '--imgformat=SVG',
            '--start=%s' % first_ts, '--end=%s' % last_ts,
            '--vertical-label=bytes/second',
            'DEF:blk_read_bps=%s:blk_read_bps:MAX' % rrdfile,
            'LINE1:blk_read_bps#0000FF:read bps',
            'DEF:blk_write_bps=%s:blk_write_bps:MAX' % rrdfile,
            'LINE1:blk_write_bps#CC0000:write bps'
        ], [
            os.path.join(outdir, 'fs_usg.svg'),
            '--title=Filesystem Usage [%s - %s]' % (from_, to),
            '--imgformat=SVG', '--start=%s' % first_ts, '--end=%s' % last_ts,
            '--vertical-label=bytes',
            'DEF:fs_used_bytes=%s:fs_used_bytes:MAX' % rrdfile,
            'LINE:fs_used_bytes#0000FF:used bytes',
            'HRULE:%s#CC0000:fs size limit '
            '(%s)' % (utils.size_to_bytes(reserved_rsrc['disk']),
                      reserved_rsrc['disk'])
        ]
    ]

    return _write_report(outdir, diagrams)


def _write_report(outdir, diagrams):
    """Save the report as an html file."""
    fs.mkdir_safe(outdir)

    for diag in diagrams:
        _gen_diagram(diag)

    utf8_reader = codecs.getreader('utf8')
    with io.open(os.path.join(outdir, 'index.html'), 'w') as f:
        f.write(
            utf8_reader(
                pkg_resources.resource_stream(
                    'treadmill.ms.resources',
                    'metrics_report.html'
                )
            ).read(size=-1)
        )

    return os.path.join(outdir, 'index.html')


def _gen_diagram(arg):
    """Generate a diagram based on the rrd file."""
    try:
        subprocess.check_call(
            [rrdutils.RRDTOOL, 'graph'] + arg, stdout=subprocess.PIPE
        )

    except subprocess.CalledProcessError as err:
        # not all datasource is present in every RRD file so let's
        # continue if one of the graph generation fails
        _LOGGER.exception(err.output)
