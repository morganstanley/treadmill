"""Treadmill application configuration.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

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
    @click.option('--runtime', envvar='TREADMILL_RUNTIME', required=True)
    @click.argument('eventfile', type=click.Path(exists=True))
    def configure(approot, runtime, eventfile):
        """Configure local manifest and schedule app to run."""
        tm_env = appenv.AppEnvironment(root=approot)

        container_dir = app_cfg.configure(tm_env, eventfile, runtime)
        _LOGGER.info('Configured %r', container_dir)

    return configure
