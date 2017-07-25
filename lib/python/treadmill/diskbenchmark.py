"""Benchmark disk IO performance"""

import ConfigParser
import logging
import os
import shutil
import subprocess
import tempfile

from enum import Enum
from xlrd import open_workbook

from treadmill import fs
from treadmill import localdiskutils
from treadmill import lvm
from treadmill import subproc
from treadmill import utils

_LOGGER = logging.getLogger(__name__)


class Metrics(Enum):
    """Benchmark metrics"""
    WRITE_BPS = 'write_bps'
    READ_BPS = 'read_bps'
    WRITE_IOPS = 'write_iops'
    READ_IOPS = 'read_iops'


# These are crucial for benchmark accuracy
BENCHMARK_IMG_SIZE = '6G'
BENCHMARK_VOLUME = '5G'
WRITE_RECORD_SIZE = '4K'
READ_RECORD_SIZE = '64K'

# In case of benchmark failure, these are default metrics
DEFAULT_BENCHMARK_RESULT = {
    Metrics.WRITE_BPS: 314572800,
    Metrics.READ_BPS: 314572800,
    Metrics.WRITE_IOPS: 64000,
    Metrics.READ_IOPS: 4000
}


_DEVICE = 'device'
_BENCHMARK_RESULT_FILE = 'result.xls'
_BENCHMARK_TMP_FILE = 'benchmark.tmp'


class IOZoneBenchmark(object):
    """Use iozone to do benchmark"""

    _cache_setting = '/proc/sys/vm/drop_caches'
    _cache_clear_magic = '3'

    def __init__(self, benchmark_base_path, benchmark_size,
                 write_record_size, read_record_size):
        self.result_file = os.path.join(benchmark_base_path,
                                        _BENCHMARK_RESULT_FILE)
        self.write_record_size = write_record_size
        self.read_record_size = read_record_size
        self.base_cmd = ['iozone', '-+n',
                         '-s', benchmark_size,
                         '-f', os.path.join(benchmark_base_path,
                                            _BENCHMARK_TMP_FILE),
                         '-b', self.result_file]

    def run(self):
        """
        Run benchmark
        :return: {metric: value, }
        """
        result = {}

        write_bps_cmd = self.base_cmd + ['-i', '0',
                                         '-r', self.write_record_size, '-w']
        read_bps_cmd = self.base_cmd + ['-i', '1',
                                        '-r', self.read_record_size]
        write_iops_cmd = write_bps_cmd + ['-O']
        read_iops_cmd = read_bps_cmd + ['-O']

        current_cache_setting = self._read_cache_setting()
        try:
            result[Metrics.WRITE_BPS] = self._run_single_benchmark(
                write_bps_cmd
            ) * 1024
            # clear buffer cache to get reasonable read performance result
            self._write_cache_setting(self._cache_clear_magic)
            self._write_cache_setting(current_cache_setting)
            result[Metrics.READ_BPS] = self._run_single_benchmark(
                read_bps_cmd
            ) * 1024
            result[Metrics.WRITE_IOPS] = self._run_single_benchmark(
                write_iops_cmd
            )
            # clear buffer cache to get reasonable read performance result
            self._write_cache_setting(self._cache_clear_magic)
            self._write_cache_setting(current_cache_setting)
            result[Metrics.READ_IOPS] = self._run_single_benchmark(
                read_iops_cmd
            )
        except Exception:  # pylint: disable=W0703
            _LOGGER.exception('iozone benchmark process failed')
            raise
        finally:
            self._write_cache_setting(current_cache_setting)

        return result

    def _read_cache_setting(self):
        with open(self._cache_setting, 'r') as fd:
            return fd.read()

    def _write_cache_setting(self, setting):
        with open(self._cache_setting, 'w') as fd:
            return fd.write(setting)

    def _run_single_benchmark(self, cmd):
        ret = subproc.call(cmd)
        if ret == 0:
            res = self._extract(self.result_file, [(5, 1)])
            return int(float(res[0][0]))

    @staticmethod
    def _extract(xls_file, coordinates):
        """Extract cell values from excel file"""
        result = []
        with open_workbook(xls_file) as wb:
            for sheet in wb.sheets():
                sheet_result = []
                for coordinate in coordinates:
                    sheet_result.append(
                        str(sheet.cell(coordinate[0], coordinate[1]).value)
                    )
                result.append(sheet_result)
        return result


class BenchmarkReader(object):
    """Benchmark reader"""

    def __init__(self, path):
        self.path = path

    def read(self):
        """
        Read benchmark
        :return: {device: {metric: value, }, }
        """
        result = {}
        config = ConfigParser.ConfigParser()
        config.read(self.path)
        for section in config.sections():
            device = config.get(section, _DEVICE)
            result[device] = {}
            for metric in Metrics:
                result[device][metric] = config.get(section, metric.value)
        return result


class BenchmarkWriter(object):
    """Benchmark writer"""

    def __init__(self, path):
        self.path = path

    def write(self, result):
        """
        Write benchmark
        :param result: {device: {metric: value, }, }
        :return:
        Sample output file format :
        [device0]
        device = 589d88bd-8098-4041-900e-7fcac18abab3
        write_bps = 314572800
        read_bps = 314572800
        write_iops = 64000
        read_iops = 4000
        """
        config = ConfigParser.ConfigParser()
        device_count = 0
        for device, metrics in result.iteritems():
            section = _DEVICE + str(device_count)
            device_count += 1
            config.add_section(section)
            config.set(section, _DEVICE, device)
            for metric, value in metrics.iteritems():
                config.set(section, metric.value, value)
        write_dir = os.path.dirname(self.path)
        if not os.path.isdir(write_dir):
            os.makedirs(write_dir)
        with tempfile.NamedTemporaryFile(
            dir=write_dir,
            delete=False
        ) as tmpfile:
            os.chmod(tmpfile.name, 0o644)
            config.write(tmpfile)
        os.rename(tmpfile.name, self.path)


def benchmark_vg(
        result_file,
        vg_name,
        underlying_device_uuid,
        volume=BENCHMARK_VOLUME,
        write_record_size=WRITE_RECORD_SIZE,
        read_record_size=READ_RECORD_SIZE,
        base_path=None,
        sys_reserve_volume='500M',
        benchmark_lv='benchmarklv'
):
    """
    Benchmark IO performance of the specified VG
    :param result_file:
        publish benchmark result to this file
    :param vg_name:
        vg to benchmark
    :param underlying_device_uuid:
        underlying device uuid of this vg
    :param volume:
        small volume leads to inaccurate benchmark,
        large volume takes too much time
    :param write_record_size:
        important for benchmarking write iops
    :param read_record_size:
        important for benchmarking read iops
    :param base_path:
        benchmark lv mount point
    :param sys_reserve_volume:
        reserved space for system usage like mke2fs
    :param benchmark_lv:
        benchmark lv name
    :return:
    """

    device = os.path.join('/dev', vg_name, benchmark_lv)
    if base_path is None:
        base_path = tempfile.mkdtemp()
        is_temp_base = True
    else:
        is_temp_base = False
    total_volume = '{}M'.format(
        utils.megabytes(volume) +
        utils.megabytes(sys_reserve_volume)
    )

    def check_available_volume():
        """Check if we have enough space for benchmark"""
        vg_status = localdiskutils.refresh_vg_status(vg_name)
        available_volume = vg_status['extent_size'] * \
            vg_status['extent_free']
        return available_volume > utils.size_to_bytes(total_volume)

    def setup_benchmark_env():
        """Prepare environment for benchmark"""
        lvm.lvcreate(
            volume=benchmark_lv,
            group=vg_name,
            size_in_bytes=utils.size_to_bytes(total_volume)
        )
        fs.create_filesystem(device)
        fs.mount_filesystem(device, base_path)

    def cleanup_benchmark_env():
        """Cleanup environment for benchmark"""
        try:
            fs.umount_filesystem(base_path)
        except subprocess.CalledProcessError:
            _LOGGER.exception('umount error')
        if is_temp_base and os.path.isdir(base_path):
            shutil.rmtree(base_path)
        try:
            lvm.lvremove(benchmark_lv, group=vg_name)
        except subprocess.CalledProcessError:
            _LOGGER.exception('lvremove error')

    def benchmark_process():
        """Do benchmark"""
        result = IOZoneBenchmark(
            base_path, volume, write_record_size, read_record_size
        ).run()
        BenchmarkWriter(
            result_file
        ).write({underlying_device_uuid: result})

    if not check_available_volume():
        _LOGGER.error('Space not enough for benchmark,'
                      'need at least %s, fallback to default metrics',
                      total_volume)
        BenchmarkWriter(
            result_file
        ).write({underlying_device_uuid: DEFAULT_BENCHMARK_RESULT})
        return

    try:
        _LOGGER.info('Setup benchmark env')
        setup_benchmark_env()
        _LOGGER.info('Start benchmark')
        benchmark_process()
    except Exception:  # pylint: disable=W0703
        _LOGGER.exception('Benchmark failed, fallback to default metrics')
        BenchmarkWriter(
            result_file
        ).write({underlying_device_uuid: DEFAULT_BENCHMARK_RESULT})
        raise
    finally:
        _LOGGER.info('Cleanup benchmark env')
        cleanup_benchmark_env()
