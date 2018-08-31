"""Useful rrd utility functions.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import socket
import time

import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

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
TIMEFRAME_TO_RRA_IDX = {'short': '0', 'long': '1'}


class RRDError(Exception):
    """RRD protocol error."""


class RRDClient:
    """RRD socket client."""

    def __init__(self, path):
        _LOGGER.info('Initializing rrdclient: %s', path)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(path)
        self.rrd = sock.makefile(mode='rw')

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

        for _ in six.moves.range(0, status):
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

    def update(self, rrdfile, data, metrics_time=None, update_str=None):
        """Updates rrd file with data, create if does not exist."""
        if metrics_time is None:
            metrics_time = int(time.time())

        rrd_update_str = update_str or ':'.join(
            [str(metrics_time), _METRICS_FMT.format(**data)]
        )
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
        _LOGGER.exception('error connecting to rrdcache')
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
        _LOGGER.exception('error connecting to rrdcache')
        return
    try:
        rrdclient.forget(rrdfile, oneway=True)
    except Exception:  # pylint: disable=W0703
        # Make it not fatal error.
        _LOGGER.exception('error sending command to rrdcache on %s',
                          rrd_socket)
    finally:
        rrdclient.rrd.close()


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
                                         '--rraindex', rra_idx]).decode()

    return epoch.strip()


def last(rrdfile, rrdtool=RRDTOOL, rrd_socket=SOCKET, exec_on_node=True):
    """
    Returns the UNIX timestamp of the most recent update of the RRD.
    """
    if exec_on_node:
        epoch = subproc.check_output([rrdtool, 'last', '--daemon',
                                      'unix:%s' % rrd_socket, rrdfile])
    else:
        epoch = subprocess.check_output([rrdtool, 'last', rrdfile]).decode()

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
