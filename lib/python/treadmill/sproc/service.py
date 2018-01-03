"""Runs the Treadmill localdisk service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import click

from treadmill import appenv
from treadmill import diskbenchmark
from treadmill import localdiskutils
from treadmill.fs import linux as fs_linux

from .. import services


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command line handler."""

    local_ctx = {}

    @click.group()
    @click.option('--root-dir', type=click.Path(exists=True),
                  required=True)
    @click.option('--watchdogs-dir', default='watchdogs')
    @click.option('--apps-dir', default='apps')
    def service(root_dir, watchdogs_dir, apps_dir):
        """Run local node service."""
        local_ctx['root-dir'] = root_dir
        local_ctx['watchdogs-dir'] = watchdogs_dir
        local_ctx['apps-dir'] = apps_dir

    @service.command()
    @click.option('--img-location',
                  help='Location of loopback image to back LVM group.')
    @click.option('--img-size', default='-2G',
                  help='Amount of local disk space to use for the image.')
    @click.option('--block-dev',
                  help='Use a block device to back LVM group.')
    @click.option('--vg-name',
                  help='Name of LVM volume group to use.')
    @click.option('--block-dev-configuration',
                  help='Block device io throughput configuration.')
    @click.option('--block-dev-read-bps',
                  help='Block device read byte per second value.')
    @click.option('--block-dev-write-bps',
                  help='Block device write byte per second value.')
    @click.option('--block-dev-read-iops', type=int,
                  help='Block device read IO per second value.')
    @click.option('--block-dev-write-iops', type=int,
                  help='Block device write IO per second value.')
    @click.option('--default-read-bps', required=True,
                  help='Default read byte per second value.')
    @click.option('--default-write-bps', required=True,
                  help='Default write byte per second value.')
    @click.option('--default-read-iops', required=True, type=int,
                  help='Default read IO per second value.')
    @click.option('--default-write-iops', required=True, type=int,
                  help='Default write IO per second value.')
    def localdisk(img_location, img_size, block_dev, vg_name,
                  block_dev_configuration,
                  block_dev_read_bps, block_dev_write_bps,
                  block_dev_read_iops, block_dev_write_iops,
                  default_read_bps, default_write_bps,
                  default_read_iops, default_write_iops):
        """Runs localdisk service."""

        impl = 'treadmill.services.localdisk_service.LocalDiskResourceService'
        root_dir = local_ctx['root-dir']
        watchdogs_dir = local_ctx['watchdogs-dir']

        svc = services.ResourceService(
            service_dir=os.path.join(root_dir, 'localdisk_svc'),
            impl=impl
        )

        block_dev_params = [block_dev_read_bps, block_dev_write_bps,
                            block_dev_read_iops, block_dev_write_iops]
        if img_location is None:
            img_location = root_dir

        # prepare block device
        if block_dev is not None:
            underlying_device_uuid = fs_linux.device_uuid(
                block_dev
            )
        else:
            underlying_device_uuid = fs_linux.blk_uuid(
                fs_linux.maj_min_to_blk(
                    *fs_linux.maj_min_from_path(
                        img_location
                    )
                )
            )
            block_dev = localdiskutils.init_block_dev(
                localdiskutils.TREADMILL_IMG,
                img_location,
                img_size
            )

        # prepare block device configuration
        read_bps = None
        write_bps = None
        read_iops = None
        write_iops = None

        # use block device config file
        if block_dev_configuration is not None and all(
                param is None for param in block_dev_params
        ):
            try:
                current_benchmark = diskbenchmark.read(
                    block_dev_configuration
                )[underlying_device_uuid]
                read_bps = current_benchmark['read_bps']
                write_bps = current_benchmark['write_bps']
                read_iops = int(current_benchmark['read_iops'])
                write_iops = int(current_benchmark['write_iops'])
            except IOError:
                _LOGGER.error(
                    'No benchmark found : %s',
                    block_dev_configuration
                )
            except (KeyError, ValueError):
                _LOGGER.error(
                    'Incorrect disk benchmark for device %s in %s',
                    underlying_device_uuid,
                    block_dev_configuration
                )

        # use block device config parameters
        if all(
                param is not None for param in block_dev_params
        ) and block_dev_configuration is None:
            read_bps = block_dev_read_bps
            write_bps = block_dev_write_bps
            read_iops = block_dev_read_iops
            write_iops = block_dev_write_iops

        if None in [read_bps, write_bps, read_iops, write_iops]:
            _LOGGER.error('Bad block dev configuration')
            read_bps = '200M'
            write_bps = '200M'
            read_iops = 3000
            write_iops = 3000

        svc.run(
            watchdogs_dir=os.path.join(root_dir,
                                       watchdogs_dir),
            block_dev=block_dev,
            vg_name=vg_name,
            read_bps=read_bps,
            write_bps=write_bps,
            read_iops=read_iops,
            write_iops=write_iops,
            default_read_bps=default_read_bps,
            default_write_bps=default_write_bps,
            default_read_iops=default_read_iops,
            default_write_iops=default_write_iops,
        )

    @service.command()
    def cgroup():
        """Runs cgroup node service."""
        root_dir = local_ctx['root-dir']
        watchdogs_dir = local_ctx['watchdogs-dir']

        svc = services.ResourceService(
            service_dir=os.path.join(root_dir, 'cgroup_svc'),
            impl='treadmill.services.cgroup_service.CgroupResourceService',
        )

        svc.run(
            watchdogs_dir=os.path.join(root_dir, watchdogs_dir),
            tm_env=appenv.AppEnvironment(root_dir),
        )

    @service.command()
    @click.option('--ext-device', default='eth0', type=str,
                  help='Externally visible network device.')
    @click.option('--ext-ip', default=None, type=str,
                  help='External network IPv4.')
    @click.option('--ext-mtu', default=None, type=int,
                  help='External network MTU.')
    @click.option('--ext-speed', default=None, type=int,
                  help='External network speeds (bps).')
    def network(ext_device, ext_ip, ext_mtu, ext_speed):
        """Runs the network service.
        """
        root_dir = local_ctx['root-dir']
        watchdogs_dir = local_ctx['watchdogs-dir']

        svc = services.ResourceService(
            service_dir=os.path.join(root_dir, 'network_svc'),
            impl='treadmill.services.network_service.NetworkResourceService',
        )

        svc.run(
            watchdogs_dir=os.path.join(root_dir,
                                       watchdogs_dir),
            ext_device=ext_device,
            ext_ip=ext_ip,
            ext_mtu=ext_mtu,
            ext_speed=ext_speed
        )

    del localdisk
    del cgroup
    del network

    return service
