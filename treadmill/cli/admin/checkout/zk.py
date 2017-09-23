"""Checkout Zookeeper ensemble.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill.checkout import zk


def init():
    """Top level command handler."""

    @click.command('zk')
    def check_zk():
        """Check Zookeeper status."""
        return lambda: zk.ZookeeperTest

    return check_zk
