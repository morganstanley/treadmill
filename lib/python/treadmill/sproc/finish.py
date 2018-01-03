"""Treadmill application finishing.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import click

from treadmill import appenv
from treadmill import cli
from treadmill import logcontext as lc
from treadmill import runtime as app_runtime
from treadmill import utils


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--runtime', envvar='TREADMILL_RUNTIME', required=True)
    @click.option('--runtime-param', type=cli.LIST, required=False)
    @click.argument('container_dir', type=click.Path(exists=True))
    def finish(approot, runtime, container_dir, runtime_param):
        """Finish treadmill application on the node."""
        # Run with finish context as finish runs in cleanup.
        with lc.LogContext(_LOGGER, os.path.basename(container_dir),
                           lc.ContainerAdapter) as log:
            log.info('finish (approot %s)', approot)
            tm_env = appenv.AppEnvironment(approot)

            param = utils.equals_list2dict(runtime_param or [])
            app_runtime.get_runtime(
                runtime, tm_env, container_dir, param
            ).finish()

    return finish
