"""Runs treadmill kernel watchdog.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import time

import click

from treadmill import kernel_watchdog as kw
from treadmill import subproc

_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler.
    """

    @click.command()
    @click.option(
        '--kernel-watchdog-root', required=True,
        help='Base directory of kernel watchdog setup.'
    )
    @click.option(
        '--reboot-script', required=True,
        help='Reboot script.'
    )
    def top(kernel_watchdog_root, reboot_script):
        """Run kernel watchdog.
        """
        kernel_watchdog = kw.KernelWatchdog(
            kernel_watchdog_root, reboot_script
        )
        try:
            kernel_watchdog.start()
        except subproc.CommandAliasError:
            _LOGGER.warning('Kernel watchdog not found')
            while True:
                time.sleep(1000000)

    return top
