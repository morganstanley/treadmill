"""Runs the Treadmill application runner."""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os
import traceback

import click

from treadmill import appenv
from treadmill import cli
from treadmill import exc
from treadmill import runtime as app_runtime
from treadmill import supervisor
from treadmill import utils

from treadmill.appcfg import abort as app_abort

_LOGGER = logging.getLogger(__name__)


def init():
    """Top level command handler."""

    @click.command()
    @click.option('--approot', type=click.Path(exists=True),
                  envvar='TREADMILL_APPROOT', required=True)
    @click.option('--runtime', envvar='TREADMILL_RUNTIME', required=True)
    @click.option('--runtime-param', type=cli.LIST, required=False)
    @click.argument('container_dir', type=click.Path(exists=True))
    def run(approot, runtime, container_dir, runtime_param=None):
        """Runs container given a container dir."""
        # Make sure container_dir is a fully resolved path.
        container_dir = os.path.realpath(container_dir)
        service = supervisor.open_service(container_dir)

        _LOGGER.info('run %r %r', approot, container_dir)

        tm_env = appenv.AppEnvironment(approot)
        param = utils.equals_list2dict(runtime_param or [])
        try:
            app_runtime.get_runtime(
                runtime, tm_env, service, param
            ).run()
        except exc.ContainerSetupError as err:
            _LOGGER.exception('Failed to start, app will be aborted.')
            app_abort.flag_aborted(service.data_dir,
                                   why=err.reason,
                                   payload=traceback.format_exc())
        except Exception as err:  # pylint: disable=W0703
            _LOGGER.exception('Failed to start, app will be aborted.')
            app_abort.flag_aborted(service.data_dir,
                                   why=app_abort.AbortedReason.UNKNOWN,
                                   payload=traceback.format_exc())

    return run
