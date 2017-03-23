"""Runs the Treadmill localdisk service."""


import logging
import os

import click

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
    @click.option('--reserve', default='2G',
                  help='Amount of local disk space to set aside.')
    @click.option('--block-dev',
                  help='Use a block device to back LVM group.')
    @click.option('--default-read-bps', required=True,
                  help='Default read byte per second value.')
    @click.option('--default-write-bps', required=True,
                  help='Default write byte per second value.')
    @click.option('--default-read-iops', required=True, type=int,
                  help='Default read IO per second value.')
    @click.option('--default-write-iops', required=True, type=int,
                  help='Default write IO per second value.')
    def localdisk(img_location, reserve, block_dev, default_read_bps,
                  default_write_bps, default_read_iops,
                  default_write_iops):
        """Runs localdisk service."""

        impl = 'treadmill.services.localdisk_service.LocalDiskResourceService'
        root_dir = local_ctx['root-dir']
        watchdogs_dir = local_ctx['watchdogs-dir']

        svc = services.ResourceService(
            service_dir=os.path.join(root_dir, 'localdisk_svc'),
            impl=impl
        )

        if block_dev is not None:
            svc.run(
                watchdogs_dir=os.path.join(root_dir,
                                           watchdogs_dir),
                block_dev=block_dev,
                default_read_bps=default_read_bps,
                default_write_bps=default_write_bps,
                default_read_iops=default_read_iops,
                default_write_iops=default_write_iops,
            )

        else:
            if img_location is None:
                img_location = root_dir
            else:
                img_location = img_location

            svc.run(
                watchdogs_dir=os.path.join(root_dir,
                                           watchdogs_dir),
                img_location=img_location,
                reserve=reserve,
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
        apps_dir = local_ctx['apps-dir']

        svc = services.ResourceService(
            service_dir=os.path.join(root_dir, 'cgroup_svc'),
            impl='treadmill.services.cgroup_service.CgroupResourceService',
        )

        svc.run(
            watchdogs_dir=os.path.join(root_dir, watchdogs_dir),
            apps_dir=os.path.join(root_dir, apps_dir),
        )

    @service.command()
    @click.option('--device', default='eth0', type=str,
                  help='Externally visible network device.')
    @click.option('--mtu', default=None, type=int,
                  help='External network MTU.')
    @click.option('--speed', default=None, type=int,
                  help='External network speeds (bps).')
    def network(device, mtu, speed):
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
            ext_device=device,
            ext_mtu=mtu,
            ext_speed=speed,
        )

    del localdisk
    del cgroup
    del network

    return service
