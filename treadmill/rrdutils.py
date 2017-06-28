"""Useful rrd utility functions.
"""

import errno
import importlib
import logging
import os
import socket
import subprocess
import time

from treadmill import fs
from treadmill import subproc


_LOGGER = logging.getLogger(__name__)

# This is rrd fields spec
_METRICS_FMT = ':'.join(['{%s}' % svc for svc in [
    'memusage',
    'softmem',
    'hardmem',
    'cputotal',
    'cpuusage',
    'cpuusage_ratio',
    'blk_read_iops',
    'blk_write_iops',
    'blk_read_bps',
    'blk_write_bps',
    'fs_used_bytes'
]])

RRDTOOL = 'rrdtool'
SOCKET = '/tmp/treadmill.rrd'

# Keeps track which RRA to be queried for the first code point according to the
# timeframces.
TIMEFRAME_TO_RRA_IDX = {"short": "0", "long": "1"}


class RRDError(Exception):
    """RRD protocol error."""


class RRDToolNotFoundError(Exception):
    """RRDtool not in the path error."""


class RRDClient(object):
    """RRD socket client."""

    def __init__(self, path):
        _LOGGER.info('Initializing rrdclient: %s', path)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(path)
        self.rrd = sock.makefile('rw')

    def command(self, line, oneway=False):
        """Sends rrd command and checks the output."""
        line = line.strip()

        if not line.startswith('UPDATE'):
            _LOGGER.info('rrd command: %s', line)
        self.rrd.write(line + '\n')
        self.rrd.flush()

        if oneway:
            self.rrd.close()
            return

        reply = self.rrd.readline()
        status, _msg = reply.split(' ', 1)
        status = int(status)

        if status < 0:
            raise RRDError(reply)

        for _ in range(0, status):
            reply = self.rrd.readline()
            _LOGGER.info('rrd reply: %s', reply)

    def create(self, rrd_file, step, interval):
        """Creates rrd file for application metrics."""
        _LOGGER.info('creating %r', rrd_file)
        fs.rm_safe(rrd_file)
        self.command(' '.join([
            'CREATE',
            rrd_file,
            '-s', str(step),
            '-b', str(int(time.time())),
            'DS:memory_usage:GAUGE:%s:0:U' % interval,
            'DS:memory_softlimit:GAUGE:%s:0:U' % interval,
            'DS:memory_hardlimit:GAUGE:%s:0:U' % interval,
            'DS:cpu_total:COUNTER:%s:0:U' % interval,
            'DS:cpu_usage:GAUGE:%s:0:U' % interval,
            'DS:cpu_ratio:GAUGE:%s:0:U' % interval,
            'DS:blk_read_iops:COUNTER:%s:0:U' % interval,
            'DS:blk_write_iops:COUNTER:%s:0:U' % interval,
            'DS:blk_read_bps:COUNTER:%s:0:U' % interval,
            'DS:blk_write_bps:COUNTER:%s:0:U' % interval,
            'DS:fs_used_bytes:GAUGE:%s:0:U' % interval,
            'RRA:MIN:0.5:{}s:20m'.format(step),
            'RRA:MIN:0.5:10m:3d',
            'RRA:MAX:0.5:{}s:20m'.format(step),
            'RRA:MAX:0.5:10m:3d',
            'RRA:AVERAGE:0.5:{}s:20m'.format(step),
            'RRA:AVERAGE:0.5:10m:3d',
        ]))

    def update(self, rrdfile, data):
        """Updates rrd file with data, create if does not exist."""
        rrd_update_str = ':'.join([str(int(time.time())),
                                   _METRICS_FMT.format(**data)])
        try:
            self.command('UPDATE %s %s' % (rrdfile, rrd_update_str))
        except RRDError:
            # TODO: rather than deleting the file, better to
            #                create new one with --source <old> option, so that
            #                data is imported. (see rrdtool create docs).
            _LOGGER.exception('Error updating: %s', rrdfile)
            fs.rm_safe(rrdfile)

    def flush(self, rrdfile, oneway=False):
        """Send flush request to the rrd cache daemon."""
        self.command('FLUSH ' + rrdfile, oneway)

    def forget(self, rrdfile, oneway=False):
        """Send forget request to the rrd cache daemon."""
        try:
            self.command('FORGET ' + rrdfile, oneway)
        except RRDError:
            # File does not exist, ignore.
            if not os.path.exists(os.path.realpath(rrdfile)):
                pass


def flush_noexc(rrdfile, rrd_socket=SOCKET):
    """Send flush request to the rrd cache daemon."""
    try:
        rrdclient = RRDClient(rrd_socket)
    except Exception:  # pylint: disable=W0703
        return
    try:
        rrdclient.flush(rrdfile, oneway=True)
    except Exception:  # pylint: disable=W0703
        # Make it not fatal error.
        _LOGGER.exception('error sending command to rrdcache on %s',
                          rrd_socket)
    finally:
        rrdclient.rrd.close()


def forget_noexc(rrdfile, rrd_socket=SOCKET):
    """Send flush request to the rrd cache daemon."""
    try:
        rrdclient = RRDClient(rrd_socket)
    except Exception:  # pylint: disable=W0703
        return
    try:
        rrdclient.forget(rrdfile, oneway=True)
    except Exception:  # pylint: disable=W0703
        # Make it not fatal error.
        _LOGGER.exception('error sending command to rrdcache on %s',
                          rrd_socket)
    finally:
        rrdclient.rrd.close()


def gen_graph(rrdfile, timeframe, rrdtool, outdir=None, reserved_rsrc=None):
    """Generate SVG images given rrd file."""
    if not outdir:
        outdir = rrdfile.rsplit('.', 1)[0]
    fs.mkdir_safe(outdir)

    # stdout, stderr -> subproc.PIPE: don't output the result of the execution
    # because it's just noise anyway
    try:
        subprocess.check_call([rrdtool, '--help'],
                              stderr=subprocess.PIPE,
                              stdout=subprocess.PIPE)
    except OSError as err:
        _LOGGER.error('%s', err)
        if err.errno == errno.ENOENT:
            raise RRDToolNotFoundError()
        raise

    first_ts = first(rrdfile, timeframe, exec_on_node=False)
    last_ts = last(rrdfile, exec_on_node=False)
    from_ = time.strftime("%b/%d %R", time.gmtime(int(first_ts)))
    to = time.strftime("%b/%d %R%z", time.gmtime(int(last_ts)))

    memory_args = [
        os.path.join(outdir, 'memory.svg'),
        "--title=Memory Usage [%s - %s]" % (from_, to),
        '--imgformat=SVG',
        '--start=%s' % first_ts,
        '--end=%s' % last_ts,
        '--vertical-label=Bytes',
        'DEF:memory_usage=%s:memory_usage:MAX' % rrdfile,
        'LINE1:memory_usage#0000FF:memory usage',
        'DEF:memory_hardlimit=%s:memory_hardlimit:MAX' % rrdfile,
        'LINE1:memory_hardlimit#CC0000:memory limit'
    ]

    cpu_usage_args = [
        os.path.join(outdir, 'cpu_usage.svg'),
        '--title=CPU Usage [%s - %s]' % (from_, to),
        '--imgformat=SVG',
        '--start=%s' % first_ts,
        '--end=%s' % last_ts,
        '--vertical-label=%',
        'DEF:cpu_usage=%s:cpu_usage:AVERAGE' % rrdfile,
        'LINE1:cpu_usage#0000FF:cpu usage',
        'HRULE:%s#CC0000:reservation of compute '
        '(%s)' % (reserved_rsrc['cpu'][:-1], reserved_rsrc['cpu']),
    ]
    cpu_ratio_args = [
        os.path.join(outdir, 'cpu_ratio.svg'),
        '--title=CPU Ratio [%s - %s]' % (from_, to),
        '--imgformat=SVG',
        '--start=%s' % first_ts,
        '--end=%s' % last_ts,
        'DEF:cpu_ratio=%s:cpu_ratio:AVERAGE' % rrdfile,
        'LINE1:cpu_ratio#0000FF:cpu ratio',
    ]
    blk_iops = [
        os.path.join(outdir, 'blk_iops.svg'),
        '--title=Block I/O [%s - %s]' % (from_, to),
        '--imgformat=SVG',
        '--start=%s' % first_ts,
        '--end=%s' % last_ts,
        '--vertical-label=operations/second',
        'DEF:blk_read_iops=%s:blk_read_iops:MAX' % rrdfile,
        'LINE1:blk_read_iops#0000FF:read iops',
        'DEF:blk_write_iops=%s:blk_write_iops:MAX' % rrdfile,
        'LINE1:blk_write_iops#CC0000:write iops'
    ]
    blk_bps = [
        os.path.join(outdir, 'blk_bps.svg'),
        '--title=Block I/O [%s - %s]' % (from_, to),
        '--imgformat=SVG',
        '--start=%s' % first_ts,
        '--end=%s' % last_ts,
        '--vertical-label=bytes/second',
        'DEF:blk_read_bps=%s:blk_read_bps:MAX' % rrdfile,
        'LINE1:blk_read_bps#0000FF:read bps',
        'DEF:blk_write_bps=%s:blk_write_bps:MAX' % rrdfile,
        'LINE1:blk_write_bps#CC0000:write bps'
    ]

    fs_usg = [
        os.path.join(outdir, 'fs_usg.svg'),
        '--title=Filesystem Usage [%s - %s]' % (from_, to),
        '--imgformat=SVG',
        '--start=%s' % first_ts,
        '--end=%s' % last_ts,
        '--vertical-label=bytes/second',
        'DEF:fs_used_bytes=%s:fs_used_bytes:MAX' % rrdfile,
        'LINE:fs_used_bytes#0000FF:used bytes',
        'HRULE:%s#CC0000:fs size limit' % reserved_rsrc['disk'],
    ]

    for arg in (memory_args, cpu_usage_args, cpu_ratio_args, blk_iops, blk_bps,
                fs_usg):
        subprocess.check_call([rrdtool, 'graph'] + arg,
                              stdout=subprocess.PIPE)

    try:
        ms_rrd = importlib.import_module('treadmill.plugins.rrdutils')
        html_header = ms_rrd.html_header()
    except ImportError as err:
        html_header = """
<head>
<script type="text/javascript"
src="http://cdn.mathjax.org/mathjax/latest/MathJax.js?config=TeX-AMS-MML_HTMLorMML"></script>
</head>
"""

    with open(os.path.join(outdir, 'index.html'), 'w+') as f:
        f.write(r"""<!DOCTYPE html><html>""" +
                html_header +
                r"""<body>
<table>
<tr><td><img src="memory.svg" /></td>
    <td>Please note that SI metric prefixes may be used on the Y axis eg.:
        $$G (giga) \Leftrightarrow 10^{9}$$
        $$M (mega) \Leftrightarrow 10^{6}$$
        $$k (kilo) \Leftrightarrow 10^{3}$$
        $$m (milli) \Leftrightarrow 10^{-3}$$
        $$u (micro) \Leftrightarrow 10^{-6}$$
        $$n (nano) \Leftrightarrow 10^{-9}$$</td>
</tr>
<tr>
<td><img src="cpu_usage.svg" /></td>
<td>$$\textrm{CPU Usage} = \frac{\textrm{used cpu  time since last measurement}
* \textrm{host's total bogomips}}{\Delta t
* \textrm{bogomips of a "virtual CPU"} * \textrm{number of cpus on the host}}
\ast 100$$<br/>
Please note: 100% is considered 1 virtual CPU
    </td>
</tr>
<tr>
<td><img src="cpu_ratio.svg" /></td>
<td>$$\textrm{CPU Ratio} = \frac{\textrm{used cpu  time since last measurement}
* \textrm{host's total bogomips}}{\Delta t * \textrm{cpu shares}
* \textrm{number of cpus on the host}}$$</td>
</tr>
<tr><td><img src="blk_iops.svg" /></td></tr>
<tr><td><img src="blk_bps.svg" /></td></tr>
<tr><td><img src="fs_usg.svg" /></td></tr>
</table>
</body>
</html>
""")


def first(rrdfile, timeframe, rrdtool=RRDTOOL, rrd_socket=SOCKET,
          exec_on_node=True):
    """
    Returns the UNIX timestamp of the first data sample entered into the RRD.
    """
    try:
        rra_idx = TIMEFRAME_TO_RRA_IDX[timeframe]
    except KeyError:
        rra_idx = TIMEFRAME_TO_RRA_IDX['short']

    if exec_on_node:
        epoch = subproc.check_output([rrdtool, 'first', rrdfile,
                                      '--daemon', 'unix:%s' % rrd_socket,
                                      '--rraindex', rra_idx])
    else:
        epoch = subprocess.check_output([rrdtool, 'first', rrdfile,
                                         '--rraindex', rra_idx])

    return epoch.strip()


def last(rrdfile, rrdtool=RRDTOOL, rrd_socket=SOCKET, exec_on_node=True):
    """
    Returns the UNIX timestamp of the most recent update of the RRD.
    """
    if exec_on_node:
        epoch = subproc.check_output([rrdtool, 'last', '--daemon',
                                      'unix:%s' % rrd_socket, rrdfile])
    else:
        epoch = subprocess.check_output([rrdtool, 'last', rrdfile])

    return epoch.strip()


def lastupdate(rrdfile, rrdtool=RRDTOOL, rrd_socket=SOCKET):
    """Get lastupdate metric"""
    last_udpate = subproc.check_output([rrdtool, 'lastupdate', '--daemon',
                                        'unix:%s' % rrd_socket, rrdfile])
    [titles, _empty, data_str] = last_udpate.strip().split('\n')
    (timestamp, value_str) = data_str.split(':')
    values = value_str.strip().split(' ')
    result = {'timestamp': int(timestamp)}

    for idx, title in enumerate(titles.strip().split(' ')):
        try:
            result[title] = int(values[idx])
        except ValueError:
            # can not be convert to int
            try:
                result[title] = float(values[idx])
            except ValueError:
                # it is possible value is 'U'
                result[title] = 0

    return result


def get_json_metrics(rrdfile, timeframe, rrdtool=RRDTOOL, rrd_socket=SOCKET):
    """Return the metrics in the rrd file as a json string."""

    _LOGGER.info('Get the metrics in JSON for %s', rrdfile)

    # the command sends a FLUSH to the rrdcached implicitly...
    cmd = [rrdtool, 'graph', '-', '--daemon', 'unix:%s' % rrd_socket,
           '--imgformat', 'JSONTIME',
           '--start=%s' % first(rrdfile, timeframe),
           '--end=%s' % last(rrdfile),
           # mem usage
           'DEF:memory_usage=%s:memory_usage:MAX' % rrdfile,
           'LINE:memory_usage:memory usage',
           # mem hardlimit
           'DEF:memory_hardlimit=%s:memory_hardlimit:MAX' % rrdfile,
           'LINE:memory_hardlimit:memory limit',
           # cpu usage
           'DEF:cpu_usage=%s:cpu_usage:AVERAGE' % rrdfile,
           'LINE:cpu_usage:cpu usage',
           # cpu ratio
           'DEF:cpu_ratio=%s:cpu_ratio:AVERAGE' % rrdfile,
           'LINE:cpu_ratio:cpu ratio',
           # blk read
           'DEF:blk_read_iops=%s:blk_read_iops:MAX' % rrdfile,
           'LINE:blk_read_iops:read iops',
           # blk write
           'DEF:blk_write_iops=%s:blk_write_iops:MAX' % rrdfile,
           'LINE:blk_write_iops:write iops',
           # blk read
           'DEF:blk_read_bps=%s:blk_read_bps:MAX' % rrdfile,
           'LINE:blk_read_bps:read bps',
           # blk write
           'DEF:blk_write_bps=%s:blk_write_bps:MAX' % rrdfile,
           'LINE:blk_write_bps:write bps',
           # fs_used_bytes
           'DEF:fs_used_bytes=%s:fs_used_bytes:MAX' % rrdfile,
           'LINE:fs_used_bytes:used bytes']

    return subproc.check_output(cmd)
