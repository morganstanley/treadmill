"""Runs the Treadmill application runner."""
from __future__ import absolute_import

import logging
import os

import click

from treadmill import appenv
from treadmill import logcontext as lc
from treadmill import runtime as app_runtime
from treadmill import utils

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
        # Intercept SIGTERM from s6 supervisor, so that initialization is not
        # left in broken state.
        with lc.LogContext(_LOGGER, os.path.basename(container_dir),
                           lc.ContainerAdapter) as log:
            terminated = utils.make_signal_flag(utils.term_signal())
            tm_env = None
            try:
                log.info('run %r %r', approot, container_dir)
                tm_env = appenv.AppEnvironment(approot)

                app_runtime.get_runtime(runtime, tm_env, container_dir).run(
                    terminated
                )

                # If we reach here, the application was terminated.

            except Exception as exc:  # pylint: disable=W0703
                if not terminated:
                    log.critical('Failed to start, app will be aborted.',
                                 exc_info=True)
                    app_abort.flag_aborted(tm_env, container_dir, exc)
                else:
                    log.info('Exception while handling term, ignore.',
                             exc_info=True)

    return run
