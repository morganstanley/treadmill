"""Implementation of treadmill admin node CLI plugin"""

import logging
import os
import click

from treadmill import diskbenchmark
from treadmill import fs
from treadmill import localdiskutils
from treadmill import subproc

_LOGGER = logging.getLogger(__name__)

_ALIAS_ERROR_MESSAGE = 'Required commands not found, ' \
                       'set proper command aliases with --aliases-path ' \
                       'or TREADMILL_ALIASES_PATH env var'


def lvm_group(parent):
    """Set up LVM on node"""

    @parent.group()
    def lvm():
        """Set up LVM on node"""
        pass

    @lvm.command()
    @click.option('--device-name', required=True,
                  type=click.Path(exists=True),
                  help='Set up LVM this device')
    def device(device_name):
        """Set up LVM on device"""
        try:
            localdiskutils.setup_device_lvm(device_name)
        except subproc.CommandAliasError:
            _LOGGER.error(_ALIAS_ERROR_MESSAGE)

    @lvm.command()
    @click.option('--image-path', required=True,
                  type=click.Path(exists=True, writable=True),
                  help='Set up LVM on an image file under this path')
    @click.option('--image-size', required=True,
                  help='Image file size')
    @click.option('--image-name', required=False,
                  default=localdiskutils.TREADMILL_IMG,
                  help='Image file name')
    def image(image_path, image_size, image_name):
        """Set up LVM on image file"""
        try:
            localdiskutils.setup_image_lvm(
                image_name,
                image_path,
                image_size
            )
        except subproc.CommandAliasError:
            _LOGGER.error(_ALIAS_ERROR_MESSAGE)

    del device
    del image


def benchmark_group(parent):
    """Benchmark node IO performance"""

    @parent.command()
    @click.option('--benchmark-publish-file', required=True,
                  type=click.Path(),
                  help='File for benchmark process to publish result')
    @click.option('--vg-name', required=False,
                  default=localdiskutils.TREADMILL_VG,
                  help='Benchmark this volume group')
    @click.option('--underlying-device-name', required=False,
                  type=click.Path(exists=True),
                  help='Underlying device name of the vg')
    @click.option('--underlying-image-path', required=False,
                  type=click.Path(exists=True),
                  help='Underlying image path of the vg')
    @click.option('--benchmark-volume', required=False,
                  default='5G',
                  help='Larger volume leads to more accurate result')
    @click.option('--write-record-size', required=False,
                  default='4K',
                  help='Important for benchmarking write iops')
    @click.option('--read-record-size', required=False,
                  default='64K',
                  help='Important for benchmarking read iops')
    def benchmark(benchmark_publish_file, vg_name,
                  underlying_device_name,
                  underlying_image_path,
                  benchmark_volume,
                  write_record_size,
                  read_record_size):
        """Benchmark node IO performance"""

        if underlying_device_name is not None:
            underlying_device_uuid = fs.device_uuid(underlying_device_name)
        elif underlying_image_path is not None:
            underlying_device_uuid = fs.device_uuid(
                fs.maj_min_to_blk(*fs.path_to_maj_min(underlying_image_path))
            )
        else:
            _LOGGER.error('No underlying device, please specify '
                          '--underlying-device-name/--underlying-image-path')
            return

        try:
            diskbenchmark.benchmark_vg(
                benchmark_publish_file,
                vg_name,
                underlying_device_uuid,
                benchmark_volume,
                write_record_size,
                read_record_size
            )
        except subproc.CommandAliasError:
            _LOGGER.error(_ALIAS_ERROR_MESSAGE)

    del benchmark


def init():
    """Return top level command handler."""

    @click.group()
    @click.option('--aliases-path', required=False,
                  envvar='TREADMILL_ALIASES_PATH',
                  help='Colon separated command alias paths')
    def node_group(aliases_path):
        """Manage Treadmill node data"""
        if aliases_path:
            os.environ['TREADMILL_ALIASES_PATH'] = aliases_path
        else:
            os.environ['TREADMILL_ALIASES_PATH'] = \
                'treadmill.bootstrap.aliases'

    lvm_group(node_group)
    benchmark_group(node_group)

    return node_group
