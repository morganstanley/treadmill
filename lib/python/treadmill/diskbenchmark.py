"""Benchmark disk IO performance.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import logging
import os
import shutil
import tempfile

import enum

import six
from six.moves import configparser

from treadmill import fs
from treadmill import localdiskutils
from treadmill import lvm
from treadmill import subproc
from treadmill import utils

from treadmill.fs import linux as fs_linux

_LOGGER = logging.getLogger(__name__)


class Metrics(enum.Enum):
    """Benchmark metrics"""
    WRITE_BPS = 'write_bps'
    READ_BPS = 'read_bps'
    WRITE_IOPS = 'write_iops'
    READ_IOPS = 'read_iops'


# These are crucial for benchmark accuracy
BENCHMARK_VOLUME = '100M'
BENCHMARK_RW_TYPE = 'rw'
BENCHMARK_JOB_NUMBER = '5'
BENCHMARK_THREAD_NUMBER = '3'
BENCHMARK_IOPS_BLOCK_SIZE = '4K'
BENCHMARK_BPS_BLOCK_SIZE = '128K'
BENCHMARK_MAX_SECONDS = '10'

_DEVICE = 'device'
_BENCHMARK_RESULT_FILE = 'benchmark.result'
_BENCHMARK_CONFIG_FILE = 'benchmark.ini'


class EqualSpaceRemover:
    """Remove spaces around equal sign in ini config.
    """

    def __init__(self, output_file):
        self.output_file = output_file

    def write(self, ini_line):
        """Wrap output"""
        self.output_file.write(ini_line.replace(' = ', '=', 1))


def benchmark(directory,
              volume=BENCHMARK_VOLUME,
              rw_type=BENCHMARK_RW_TYPE,
              job_number=BENCHMARK_JOB_NUMBER,
              thread_number=BENCHMARK_THREAD_NUMBER,
              block_size=BENCHMARK_IOPS_BLOCK_SIZE,
              max_seconds=BENCHMARK_MAX_SECONDS):
    """Use fio to do benchmark.
    """
    result = {}
    config_file = os.path.join(directory, _BENCHMARK_CONFIG_FILE)
    result_file = os.path.join(directory, _BENCHMARK_RESULT_FILE)

    # prepare fio config
    config = configparser.SafeConfigParser()
    global_section = 'global'
    config.add_section(global_section)
    config.set(global_section, 'group_reporting', '1')
    config.set(global_section, 'unlink', '1')
    config.set(global_section, 'time_based', '1')
    config.set(global_section, 'direct', '1')
    config.set(global_section, 'size', volume)
    config.set(global_section, 'rw', rw_type)
    config.set(global_section, 'numjobs', job_number)
    config.set(global_section, 'iodepth', thread_number)
    config.set(global_section, 'bs', block_size)
    config.set(global_section, 'runtime', max_seconds)
    drive_section = 'drive'
    config.add_section(drive_section)
    config.set(drive_section, 'directory', directory)
    fs.write_safe(
        config_file,
        lambda f: config.write(EqualSpaceRemover(f))
    )

    # start fio
    ret = subproc.call(
        ['fio', config_file, '--norandommap',
         '--minimal', '--output', result_file]
    )

    # parse fio terse result
    # http://fio.readthedocs.io/en/latest/fio_doc.html#terse-output
    if ret == 0:
        with io.open(result_file) as fp:
            metric_list = fp.read().split(';')
            result[Metrics.READ_BPS.value] = int(
                float(metric_list[6]) * 1024
            )
            result[Metrics.READ_IOPS.value] = int(metric_list[7])
            result[Metrics.WRITE_BPS.value] = int(
                float(metric_list[47]) * 1024
            )
            result[Metrics.WRITE_IOPS.value] = int(metric_list[48])

    return result


def read(benchmark_result_file):
    """
    Read benchmark
    :param benchmark_result_file: benchmark result file
    :return: {device: {metric: value, }, }
    """
    result = {}
    config = configparser.SafeConfigParser()
    with io.open(benchmark_result_file) as fp:
        config.readfp(fp)  # pylint: disable=deprecated-method
    for section in config.sections():
        try:
            device = config.get(section, _DEVICE)
            result[device] = {}
            for metric in Metrics:
                result[device][metric.value] = config.get(
                    section,
                    metric.value
                )
        except configparser.NoOptionError:
            _LOGGER.error(
                'Incorrect section in %s',
                benchmark_result_file
            )

    return result


def write(benchmark_result_file, result):
    """Write benchmark result.

    Sample output file format:
        [device0]
        device = 589d88bd-8098-4041-900e-7fcac18abab3
        write_bps = 314572800
        read_bps = 314572800
        write_iops = 64000
        read_iops = 4000

    :param benchmark_result_file:
        benchmark result file
    :param result:
        {device: {metric: value, }, }
    """
    config = configparser.SafeConfigParser()
    device_count = 0
    for device, metrics in six.iteritems(result):
        section = _DEVICE + six.text_type(device_count)
        device_count += 1
        config.add_section(section)
        config.set(section, _DEVICE, device)
        for metric, value in six.iteritems(metrics):
            config.set(section, metric, six.text_type(value))

    fs.write_safe(
        benchmark_result_file,
        config.write,
        permission=0o644
    )


def benchmark_vg(vg_name,
                 volume=BENCHMARK_VOLUME,
                 rw_type=BENCHMARK_RW_TYPE,
                 job_number=BENCHMARK_JOB_NUMBER,
                 thread_number=BENCHMARK_THREAD_NUMBER,
                 block_size=BENCHMARK_IOPS_BLOCK_SIZE,
                 max_seconds=BENCHMARK_MAX_SECONDS,
                 base_path=None,
                 sys_reserve_volume='500M',
                 benchmark_lv='benchmarklv'):
    """Benchmark IO performance of the specified VG

    :param vg_name:
        vg to benchmark
    :param volume:
        small volume leads to inaccurate benchmark,
        large volume takes too much time
    :param rw_type:
        fio rw option
    :param job_number:
        fio numjobs option
    :param thread_number:
        fio iodepth option
    :param block_size:
        fio bs option
    :param max_seconds:
        fio runtime option
    :param base_path:
        benchmark lv mount point
    :param sys_reserve_volume:
        reserved space for system usage like mke2fs
    :param benchmark_lv:
        benchmark lv name
    """

    device = os.path.join('/dev', vg_name, benchmark_lv)
    if base_path is None:
        base_path = tempfile.mkdtemp()
        is_temp_base = True
    else:
        is_temp_base = False
    total_volume = '{}M'.format(
        utils.megabytes(volume) * int(job_number) +
        utils.megabytes(sys_reserve_volume)
    )

    def check_available_volume():
        """Check if we have enough space for benchmark.
        """
        vg_status = localdiskutils.refresh_vg_status(vg_name)
        available_volume = vg_status['extent_size'] * \
            vg_status['extent_free']
        return available_volume > utils.size_to_bytes(total_volume)

    def setup_benchmark_env():
        """Prepare environment for benchmark.
        """
        lvm.lvcreate(
            volume=benchmark_lv,
            group=vg_name,
            size_in_bytes=utils.size_to_bytes(total_volume)
        )
        fs_linux.blk_fs_create(device)
        fs_linux.mount_filesystem(device, base_path, fs_type='ext4')

    def cleanup_benchmark_env():
        """Cleanup environment after benchmark.
        """
        try:
            fs_linux.umount_filesystem(base_path)
        except OSError:
            _LOGGER.exception('umount error')
        if is_temp_base and os.path.isdir(base_path):
            shutil.rmtree(base_path)
        try:
            lvm.lvremove(benchmark_lv, group=vg_name)
        except subproc.CalledProcessError:
            _LOGGER.exception('lvremove error')

    if not check_available_volume():
        _LOGGER.error('Space not enough for benchmark,'
                      'need at least %s',
                      total_volume)
        return None

    try:
        _LOGGER.info('Setup benchmark env')
        setup_benchmark_env()
        _LOGGER.info('Start benchmark')
        return benchmark(base_path, volume, rw_type, job_number,
                         thread_number, block_size, max_seconds)
    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Benchmark failed')
        raise
    finally:
        _LOGGER.info('Cleanup benchmark env')
        cleanup_benchmark_env()
