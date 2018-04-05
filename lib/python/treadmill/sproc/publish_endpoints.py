"""Publish local endpoints to Zookeeper."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import appenv
from treadmill import context
from treadmill import endpoints


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--instance', help='Publisher instance.')
    def run(approot, instance):
        """Starts discovery publisher process."""
        tm_env = appenv.AppEnvironment(approot)
        publisher = endpoints.EndpointPublisher(tm_env.endpoints_dir,
                                                context.GLOBAL.zk.conn,
                                                instance=instance)
        publisher.run()

    return run
