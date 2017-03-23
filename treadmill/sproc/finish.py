"""Treadmill application finishing."""


import logging
import os

import click

from .. import appmgr
from .. import context
from .. import logcontext as lc
from ..appmgr import finish as app_finish


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.argument('container_dir', type=click.Path(exists=True))
    def finish(approot, container_dir):
        """Finish treadmill application on the node."""
        with lc.LogContext(_LOGGER, os.path.basename(container_dir),
                           lc.ContainerAdapter) as log:
            log.logger.info('finish (approot %s)', approot)
            app_env = appmgr.AppEnvironment(approot)
            app_finish.finish(app_env, context.GLOBAL.zk.conn, container_dir)

    return finish
