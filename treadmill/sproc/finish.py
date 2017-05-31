"""Treadmill application finishing."""

import logging
import os

import click

from treadmill import appenv
from treadmill import logcontext as lc
from treadmill import runtime as app_runtime


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--runtime', default=app_runtime.DEFAULT_RUNTIME)
    @click.argument('container_dir', type=click.Path(exists=True))
    def finish(approot, runtime, container_dir):
        """Finish treadmill application on the node."""

        # Run with finish context as finish runs in cleanup.
        with lc.LogContext(_LOGGER, os.path.basename(container_dir),
                           lc.ContainerAdapter) as log:
            log.info('finish (approot %s)', approot)
            tm_env = appenv.AppEnvironment(approot)

            app_runtime.get_runtime(runtime, tm_env, container_dir).finish()

    return finish
