"""Runs Treadmill application presence daemon."""
from __future__ import absolute_import

import logging

import click

from treadmill import appenv
from treadmill import context
from treadmill import runtime as app_runtime
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)

#: 3 hours
_TICKETS_REFRESH_INTERVAL = 60 * 60 * 3


def init():
    """App main."""

    @click.group(name='presence')
    def presence_grp():
        """Register container/app presence."""
        context.GLOBAL.zk.conn.add_listener(zkutils.exit_on_lost)

    @presence_grp.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--runtime', default=app_runtime.DEFAULT_RUNTIME)
    @click.option('--refresh-interval', type=int,
                  default=_TICKETS_REFRESH_INTERVAL)
    @click.argument('manifest', type=click.Path(exists=True))
    @click.argument('container-dir', type=click.Path(exists=True))
    def register(approot, runtime, refresh_interval, manifest,
                 container_dir):
        """Register container presence."""
        tm_env = appenv.AppEnvironment(approot)

        app_runtime.get_runtime(runtime, tm_env, container_dir).register(
            manifest, refresh_interval
        )

    @presence_grp.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--runtime', default=app_runtime.DEFAULT_RUNTIME)
    @click.argument('manifest', type=click.Path(exists=True))
    @click.argument('container-dir', type=click.Path(exists=True))
    def monitor(approot, runtime, manifest, container_dir):
        """Monitor container services."""
        tm_env = appenv.AppEnvironment(approot)

        app_runtime.get_runtime(runtime, tm_env, container_dir).monitor(
            manifest
        )

    del register
    del monitor
    return presence_grp
