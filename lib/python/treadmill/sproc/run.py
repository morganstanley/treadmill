"""Runs the Treadmill application runner."""
from __future__ import absolute_import

import signal

import logging

import click

from .. import appmgr
from .. import utils
from ..appmgr import run as app_run
from ..appmgr import abort as app_abort


_LOGGER = logging.getLogger()


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.argument('container_dir', type=click.Path(exists=True))
    def run(approot, container_dir):
        """Runs container given a container dir."""
        # Intercept SIGTERM from s6 supervisor, so that initialization is not
        # left in broken state.
        terminated = utils.make_signal_flag(signal.SIGTERM)
        try:
            _LOGGER.info('run %r %r', approot, container_dir)
            app_env = appmgr.AppEnvironment(approot)

            watchdog = app_run.create_watchdog(app_env, container_dir)

            # Apply memsory limits first thing after start, so that app_run
            # does not consume memory from treadmill/core.
            app_run.apply_cgroup_limits(app_env, container_dir)

            if not terminated:
                app_run.run(app_env, container_dir, watchdog, terminated)

            # If we reach here, the application was terminated.

        except Exception as exc:  # pylint: disable=W0703
            if not terminated:
                _LOGGER.critical('Failed to start, app will be aborted.',
                                 exc_info=True)
                app_abort.flag_aborted(app_env, container_dir, exc)
            else:
                _LOGGER.info('Exception while handling term, ignore.',
                             exc_info=True)

        finally:
            watchdog.remove()

    return run
