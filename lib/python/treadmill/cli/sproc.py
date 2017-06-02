"""Implementation of treadmill-admin CLI plugin."""
from __future__ import absolute_import

import logging
import os

import click

from treadmill import cli
from treadmill import cgroups
from treadmill import cgutils

_LOGGER = logging.getLogger(__name__)


def _configure_core_cgroups(service_name):
    """Configure service specific cgroups."""
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

    @click.group(cls=cli.make_multi_command('treadmill.sproc'))
    @click.option('--cgroup',
                  help='Create separate cgroup for the service.')
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--zookeeper', required=False,
                  envvar='TREADMILL_ZOOKEEPER',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.pass_context
    def run(ctx, cgroup):
        """Run system processes"""
        # Default logging to daemon.conf, at CRITICAL, unless --debug
        cli.init_logger('daemon.conf')

        log_level = None
        if ctx.obj.get('logging.debug'):
            log_level = logging.DEBUG
        else:
            log_level = logging.DEBUG

        logging.getLogger('kazoo').setLevel(log_level)
        logging.getLogger('treadmill').setLevel(log_level)
        logging.getLogger().setLevel(log_level)

        if cgroup:
            if cgroup == '.':
                service_name = os.path.basename(os.path.realpath(cgroup))
            else:
                service_name = cgroup
            _configure_core_cgroups(service_name)

    return run
