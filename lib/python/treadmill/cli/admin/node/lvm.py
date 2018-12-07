"""Implementation of treadmill admin node CLI plugin
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import click

from treadmill import localdiskutils
from treadmill import subproc

_LOGGER = logging.getLogger(__name__)

_ALIAS_ERROR_MESSAGE = 'Required commands not found, ' \
                       'set proper command aliases with --aliases-path ' \
                       'or TREADMILL_ALIASES_PATH env var'


def init():
    """Set up LVM on node"""

    ctx = {}

    @click.group()
    @click.option('--vg-name', required=False,
                  default=localdiskutils.TREADMILL_VG,
                  help='Set up LVM on this volume group')
    def lvm(vg_name):
        """Set up LVM on node"""
        ctx['vg_name'] = vg_name

    @lvm.command()
    @click.option('--device-name', required=True,
                  type=click.Path(exists=True),
                  help='Set up LVM this device')
    def device(device_name):
        """Set up LVM on device"""
        try:
            localdiskutils.setup_device_lvm(device_name, ctx['vg_name'])
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
                image_size,
                ctx['vg_name']
            )
        except subproc.CommandAliasError:
            _LOGGER.error(_ALIAS_ERROR_MESSAGE)

    del device
    del image

    return lvm
