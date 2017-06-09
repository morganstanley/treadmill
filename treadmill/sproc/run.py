"""Runs the Treadmill application runner.
"""

import logging
import os

import click

from treadmill import appenv
from treadmill import runtime as app_runtime

from treadmill.appcfg import abort as app_abort

_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--runtime', default=app_runtime.DEFAULT_RUNTIME)
    @click.argument('container_dir', type=click.Path(exists=True))
    def run(approot, runtime, container_dir):
        """Runs container given a container dir."""
        # Make sure container_dir is a fully resolved path.
        container_dir = os.path.realpath(container_dir)

        _LOGGER.info('run %r %r', approot, container_dir)

        tm_env = appenv.AppEnvironment(approot)
        try:
            app_runtime.get_runtime(runtime, tm_env, container_dir).run()

        except Exception as exc:  # pylint: disable=W0703
            _LOGGER.exception('Failed to start, app will be aborted.')
            app_abort.flag_aborted(tm_env, container_dir, exc)

    return run
