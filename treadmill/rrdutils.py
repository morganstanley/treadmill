"""Useful rrd utility functions."""


import errno

import logging
import time
import os
import socket

from . import fs
from . import metrics
from . import sysinfo


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


class RRDError(Exception):
    """RRD protocol error."""


class RRDClient(object):
    """RRD socket client."""

    def __init__(self, path):
        _LOGGER.info('Initializing rrdclient: %s', path)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(path)
        self.rrd = sock.makefile()

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


def flush_noexc(rrdfile, rrd_socket='/tmp/treadmill.rrd'):
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


def forget_noexc(rrdfile, rrd_socket='/tmp/treadmill.rrd'):
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


def app_metrics(cgrp, blkio_major_minor=None):
    """Returns app metrics or empty dict if app not found."""
    result = {
        'memusage': 0,
        'softmem': 0,
        'hardmem': 0,
        'cpuusage': 0,
        'cpuusage_ratio': 0,
        'blk_read_iops': 0,
        'blk_write_iops': 0,
        'blk_read_bps': 0,
        'blk_write_bps': 0,
    }

    meminfo = sysinfo.mem_info()
    meminfo_total_bytes = meminfo.total * 1024

    try:
        memusage, softmem, hardmem = metrics.read_memory_stats(cgrp)
        if softmem > meminfo_total_bytes:
            softmem = meminfo_total_bytes

        if hardmem > meminfo_total_bytes:
            hardmem = meminfo_total_bytes

        result.update({
            'memusage': memusage,
            'softmem': softmem,
            'hardmem': hardmem,
        })

        cpuusage, _, cpuusage_ratio = metrics.read_cpu_stats(cgrp)
        result.update({
            'cpuusage': cpuusage,
            'cpuusage_ratio': cpuusage_ratio,
        })

        blkusage = metrics.read_blkio_stats(cgrp, blkio_major_minor)
        result.update({
            'blk_read_iops': blkusage['read_iops'],
            'blk_write_iops': blkusage['write_iops'],
            'blk_read_bps': blkusage['read_bps'],
            'blk_write_bps': blkusage['write_bps'],
        })

    except IOError as err:
        if err.errno != errno.ENOENT:
            raise err

    except OSError as err:
        if err.errno != errno.ENOENT:
            raise err

    return result


def gen_graph(rrdfile, rrdtool, outdir=None, show_mem_limit=True):
    """Generate PNG images given rrd file."""
    if not outdir:
        outdir = rrdfile.rsplit('.', 1)[0]
    fs.mkdir_safe(outdir)

    memory_args = [
        os.path.join(outdir, 'memory.png'),
        'DEF:memory_usage=%s:memory_usage:MAX' % rrdfile,
        'LINE1:memory_usage#0000FF:"memory usage"',
    ]
    if show_mem_limit:
        memory_args.extend([
            'DEF:memory_hardlimit=%s:memory_hardlimit:MAX' % rrdfile,
            'LINE1:memory_hardlimit#CC0000:"memory limit"'
        ])

    cpu_usage_args = [
        os.path.join(outdir, 'cpu_usage.png'),
        'DEF:cpu_usage=%s:cpu_usage:AVERAGE' % rrdfile,
        'LINE1:cpu_usage#0000FF:"cpu usage"',
    ]
    cpu_ratio_args = [
        os.path.join(outdir, 'cpu_ratio.png'),
        'DEF:cpu_ratio=%s:cpu_ratio:AVERAGE' % rrdfile,
        'LINE1:cpu_ratio#0000FF:"cpu ratio"',
    ]
    blk_iops = [
        os.path.join(outdir, 'blk_iops.png'),
        'DEF:blk_read_iops=%s:blk_read_iops:MAX' % rrdfile,
        'LINE1:blk_read_iops#0000FF:"read iops"',
        'DEF:blk_write_iops=%s:blk_write_iops:MAX' % rrdfile,
        'LINE1:blk_write_iops#CC0000:"write iops"'
    ]
    blk_bps = [
        os.path.join(outdir, 'blk_bps.png'),
        'DEF:blk_read_bps=%s:blk_read_bps:MAX' % rrdfile,
        'LINE1:blk_read_bps#0000FF:"read bps"',
        'DEF:blk_write_bps=%s:blk_write_bps:MAX' % rrdfile,
        'LINE1:blk_write_bps#CC0000:"write bps"'
    ]

    os.system(' '.join([rrdtool, 'graph'] + memory_args))
    os.system(' '.join([rrdtool, 'graph'] + cpu_usage_args))
    os.system(' '.join([rrdtool, 'graph'] + cpu_ratio_args))
    os.system(' '.join([rrdtool, 'graph'] + blk_iops))
    os.system(' '.join([rrdtool, 'graph'] + blk_bps))

    with open(os.path.join(outdir, 'index.html'), 'w+') as f:
        f.write("""
<html>
<body>
<img src="memory.png" /><br/>
<img src="cpu_usage.png" /><br/>
<img src="cpu_ratio.png" /><br/>
<img src="blk_iops.png" /><br/>
<img src="blk_bps.png" /><br/>
</body>
</html>
""")
