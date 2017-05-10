"""Useful rrd utility functions."""


import errno

import logging
import time
import os
import socket
import subprocess

from treadmill import fs
from treadmill import subproc


_LOGGER = logging.getLogger(__name__)

# This is rrd fields spec
_METRICS_FMT = ':'.join(['{%s}' % svc for svc in [
    'memusage',
    'softmem',
    'hardmem',
    'cpuusage',
    'cpuusage_ratio',
    'blk_read_iops',
    'blk_write_iops',
    'blk_read_bps',
    'blk_write_bps'
]])

RRDTOOL = 'rrdtool'
SOCKET = '/tmp/treadmill.rrd'


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
        status, _msg = reply.split(b' ', 1)
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
            'DS:cpu_usage:GAUGE:%s:0:U' % interval,
            'DS:cpu_ratio:GAUGE:%s:0:U' % interval,
            'DS:blk_read_iops:COUNTER:%s:0:U' % interval,
            'DS:blk_write_iops:COUNTER:%s:0:U' % interval,
            'DS:blk_read_bps:COUNTER:%s:0:U' % interval,
            'DS:blk_write_bps:COUNTER:%s:0:U' % interval,
            'RRA:MIN:0.5:1:120',
            'RRA:MIN:0.5:120:360',
            'RRA:MAX:0.5:1:120',
            'RRA:MAX:0.5:120:360',
            'RRA:AVERAGE:0.5:1:120',
            'RRA:AVERAGE:0.5:120:360',
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
    rrdclient = RRDClient(rrd_socket)
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
    rrdclient = RRDClient(rrd_socket)
    try:
        rrdclient.forget(rrdfile, oneway=True)
    except Exception:  # pylint: disable=W0703
        # Make it not fatal error.
        _LOGGER.exception('error sending command to rrdcache on %s',
                          rrd_socket)
    finally:
        rrdclient.rrd.close()


def gen_graph(rrdfile, rrdtool, outdir=None, show_mem_limit=True):
    """Generate SVG images given rrd file."""
    if not outdir:
        outdir = rrdfile.rsplit('.', 1)[0]
    fs.mkdir_safe(outdir)

    # stdout, stderr -> subproc.PIPE: don't print the result of the execution
    # because it's just noise anyway
    try:
        subprocess.check_call(['rrdtool', '--help'],
                              stderr=subprocess.PIPE,
                              stdout=subprocess.PIPE)
    except OSError as err:
        _LOGGER.error('%s', err)
        if err.errno == errno.ENOENT:
            raise RRDToolNotFoundError()
        raise

    first_ts = subprocess.check_output([rrdtool, 'first', rrdfile])
    last_ts = subprocess.check_output([rrdtool, 'last', rrdfile])

    memory_args = [
        os.path.join(outdir, 'memory.svg'),
        '--imgformat=SVG',
        '--start=%s' % first_ts,
        '--end=%s' % last_ts,
        'DEF:memory_usage=%s:memory_usage:MAX' % rrdfile,
        'LINE1:memory_usage#0000FF:"memory usage"',
    ]
    if show_mem_limit:
        memory_args.extend([
            'DEF:memory_hardlimit=%s:memory_hardlimit:MAX' % rrdfile,
            'LINE1:memory_hardlimit#CC0000:"memory limit"'
        ])

    cpu_usage_args = [
        os.path.join(outdir, 'cpu_usage.svg'),
        '--imgformat=SVG',
        '--start=%s' % first_ts,
        '--end=%s' % last_ts,
        'DEF:cpu_usage=%s:cpu_usage:AVERAGE' % rrdfile,
        'LINE1:cpu_usage#0000FF:"cpu usage"',
    ]
    cpu_ratio_args = [
        os.path.join(outdir, 'cpu_ratio.svg'),
        '--imgformat=SVG',
        '--start=%s' % first_ts,
        '--end=%s' % last_ts,
        'DEF:cpu_ratio=%s:cpu_ratio:AVERAGE' % rrdfile,
        'LINE1:cpu_ratio#0000FF:"cpu ratio"',
    ]
    blk_iops = [
        os.path.join(outdir, 'blk_iops.svg'),
        '--imgformat=SVG',
        '--start=%s' % first_ts,
        '--end=%s' % last_ts,
        'DEF:blk_read_iops=%s:blk_read_iops:MAX' % rrdfile,
        'LINE1:blk_read_iops#0000FF:"read iops"',
        'DEF:blk_write_iops=%s:blk_write_iops:MAX' % rrdfile,
        'LINE1:blk_write_iops#CC0000:"write iops"'
    ]
    blk_bps = [
        os.path.join(outdir, 'blk_bps.svg'),
        '--imgformat=SVG',
        '--start=%s' % first_ts,
        '--end=%s' % last_ts,
        'DEF:blk_read_bps=%s:blk_read_bps:MAX' % rrdfile,
        'LINE1:blk_read_bps#0000FF:"read bps"',
        'DEF:blk_write_bps=%s:blk_write_bps:MAX' % rrdfile,
        'LINE1:blk_write_bps#CC0000:"write bps"'
    ]

    for arg in memory_args, cpu_usage_args, cpu_ratio_args, blk_iops, blk_bps:
        subprocess.check_call([rrdtool, 'graph'] + arg,
                              stdout=subprocess.PIPE)

    with open(os.path.join(outdir, 'index.html'), 'w+') as f:
        f.write("""
<html>
<body>
<img src="memory.svg" /><br/>
<img src="cpu_usage.svg" /><br/>
<img src="cpu_ratio.svg" /><br/>
<img src="blk_iops.svg" /><br/>
<img src="blk_bps.svg" /><br/>
</body>
</html>
""")


def first(rrdfile, rrdtool=RRDTOOL, rrd_socket=SOCKET):
    """
    Returns the UNIX timestamp of the first data sample entered into the RRD.
    """
    epoch = subproc.check_output([rrdtool, 'first', '--daemon',
                                  'unix:%s' % rrd_socket, rrdfile])
    return epoch.strip()


def last(rrdfile, rrdtool=RRDTOOL, rrd_socket=SOCKET):
    """
    Returns the UNIX timestamp of the most recent update of the RRD.
    """
    epoch = subproc.check_output([rrdtool, 'last', '--daemon',
                                  'unix:%s' % rrd_socket, rrdfile])
    return epoch.strip()


def get_json_metrics(rrdfile, rrdtool=RRDTOOL, rrd_socket=SOCKET):
    """Return the metrics in the rrd file as a json string."""

    _LOGGER.info('Get the metrics in JSON for %s', rrdfile)

    # the command sends a FLUSH to the rrdcached implicitly...
    cmd = [rrdtool, 'graph', '-', '--daemon', 'unix:%s' % rrd_socket,
           '--imgformat', 'JSONTIME',
           '--start=%s' % first(rrdfile),
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
           'LINE:blk_write_bps:write bps']

    return subproc.check_output(cmd)
