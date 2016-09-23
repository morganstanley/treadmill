"""Treadmill application finishing."""
from __future__ import absolute_import

import logging

import click

from .. import appmgr
from .. import context
from ..appmgr import finish as app_finish


_LOGGER = logging.getLogger()


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.argument('container_dir', type=click.Path(exists=True))
    def finish(approot, container_dir):
        """Finish treadmill application on the node."""
        _LOGGER.info('finish %s %s', approot, container_dir)
        app_env = appmgr.AppEnvironment(approot)
        app_finish.finish(app_env, context.GLOBAL.zk.conn, container_dir)

    return finish
