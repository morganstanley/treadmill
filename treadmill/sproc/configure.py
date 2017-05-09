"""Treadmill application configuration."""


import logging

import click

from treadmill import appenv

from treadmill.appcfg import configure as app_cfg


_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.argument('eventfile', type=click.Path(exists=True))
    def configure(approot, eventfile):
        """Configure local manifest and schedule app to run."""
        tm_env = appenv.AppEnvironment(root=approot)

        container_dir = app_cfg.configure(tm_env, eventfile)
        _LOGGER.info('Configured %r', container_dir)

    return configure
