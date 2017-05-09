"""Checkout Zookeeper ensemble."""

import click

from treadmill.checkout import zk


def init():
    """Top level command handler."""

    @click.command('zk')
    def check_zk():
        """Check Zookeeper status."""
        return lambda: zk.ZookeeperTest

    return check_zk
