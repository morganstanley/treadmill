"""Checkout Zookeeper ensemble."""
from __future__ import absolute_import

import click

from treadmill.tests import zk


def init():
    """Top level command handler."""

    @click.command('zk')
    def check_zk():
        """Check Zookeeper status."""
        return lambda: zk.ZookeeperTest

    return check_zk
