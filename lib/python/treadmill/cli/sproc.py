"""Treadmill system processes launcher.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import click

from treadmill import cli
from treadmill import osnoop

_LOGGER = logging.getLogger(__name__)


@osnoop.windows
def _configure_core_cgroups(service_name):
    """Configure service specific cgroups."""
    from treadmill import cgroups
    from treadmill import cgutils

    if service_name == '.':
        service_name = os.path.basename(os.path.realpath(service_name))

    group = os.path.join('treadmill/core', service_name)
    # create group directory
    for subsystem in ['memory', 'cpu', 'cpuacct', 'blkio']:
        _LOGGER.info('creating and joining: %s/%s', subsystem, group)
        cgutils.create(subsystem, group)
        cgroups.join(subsystem, group)

    # set memory usage limits
    memlimits = ['memory.limit_in_bytes',
                 'memory.memsw.limit_in_bytes',
                 'memory.soft_limit_in_bytes']
    for limit in memlimits:
        parent_limit = cgroups.get_value('memory', 'treadmill/core', limit)
        _LOGGER.info('setting %s: %s', limit, parent_limit)
        cgroups.set_value('memory', group, limit, parent_limit)

    # set cpu share limits
    cpulimits = ['cpu.shares']
    for limit in cpulimits:
        parent_limit = cgroups.get_value('cpu', 'treadmill/core', limit)
        _LOGGER.info('setting %s: %s', limit, parent_limit)
        cgroups.set_value('cpu', group, limit, parent_limit)


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_commands('treadmill.sproc'))
    @click.option('--cgroup',
                  help='Create separate cgroup for the service.')
    @click.option('--logging-conf', default='daemon.conf',
                  help='Logging config file to use.')
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--zookeeper', required=False,
                  envvar='TREADMILL_ZOOKEEPER',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.pass_context
    def run(ctx, cgroup, logging_conf):
        """Run system processes"""
        # Default logging to daemon.conf, at CRITICAL, unless --debug
        cli.init_logger(logging_conf)

        log_level = None
        if ctx.obj.get('logging.debug'):
            log_level = logging.DEBUG
        else:
            log_level = logging.DEBUG

        logging.getLogger('kazoo').setLevel(logging.INFO)
        logging.getLogger('treadmill').setLevel(log_level)
        logging.getLogger().setLevel(log_level)

        if cgroup:
            _configure_core_cgroups(cgroup)

    return run
