"""Treadmill install dependencies"""

import logging
import click
from treadmill import TREADMILL
from subprocess import call

_LOGGER = logging.getLogger(__name__)


def init():
    """Install treadmill dependencies"""

    @click.command()
    def pid1():
        """Install dependencies"""
        call(TREADMILL + '/local/linux/scripts/install_pid1.sh')

    return pid1
