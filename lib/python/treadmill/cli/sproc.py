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
from treadmill import logging as tl
from treadmill import osnoop

_LOGGER = logging.getLogger(__name__)


@osnoop.windows
def _configure_service_cgroups(cgroup, root_cgroup):
    """Configure service specific cgroups."""
    from treadmill import cgroups
    from treadmill import cgutils

    if cgroup == '.':
        cgroup = os.path.basename(os.path.realpath('.'))

    if os.path.isabs(cgroup):
        group = os.path.join(root_cgroup, cgroup.lstrip('/'))
    else:
        group = os.path.join(
            cgutils.core_group_name(root_cgroup), cgroup
        )
    parent = os.path.dirname(group)

    # create group directory
    for subsystem in ['memory', 'cpu', 'cpuacct', 'cpuset', 'blkio']:
        _LOGGER.info('creating : %s/%s', subsystem, group)
        cgutils.create(subsystem, group)

    # set memory usage limits
    memlimits = ['memory.limit_in_bytes',
                 'memory.memsw.limit_in_bytes',
                 'memory.soft_limit_in_bytes']
    for limit in memlimits:
        parent_limit = cgroups.get_value('memory', parent, limit)
        _LOGGER.info('setting %s: %s', limit, parent_limit)
        cgroups.set_value('memory', group, limit, parent_limit)

    # set cpu share limits
    cpulimits = ['cpu.shares']
    for limit in cpulimits:
        parent_limit = cgroups.get_value('cpu', parent, limit)
        _LOGGER.info('setting %s: %s', limit, parent_limit)
        cgroups.set_value('cpu', group, limit, parent_limit)

    # set cpuset
    cgroups.inherit_value('cpuset', group, 'cpuset.cpus')
    cgroups.inherit_value('cpuset', group, 'cpuset.mems')

    # join cgroup
    for subsystem in ['memory', 'cpu', 'cpuacct', 'cpuset', 'blkio']:
        _LOGGER.info('joining: %s/%s', subsystem, group)
        cgroups.join(subsystem, group)


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_commands('treadmill.sproc'))
    @click.option('--cgroup',
                  help='Create separate cgroup for the service.')
    @click.option('--logging-conf', default='daemon.json',
                  help='Logging config file to use.')
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--zookeeper', required=False,
                  envvar='TREADMILL_ZOOKEEPER',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--root-cgroup', default='treadmill',
                  envvar='TREADMILL_ROOT_CGROUP', required=False)
    @click.pass_context
    def run(ctx, cgroup, logging_conf, root_cgroup):
        """Run system processes"""
        # Default logging to daemon.conf, at CRITICAL, unless --debug
        cli.init_logger(logging_conf)
        ctx.obj['ROOT_CGROUP'] = root_cgroup

        log_level = None
        if ctx.obj.get('logging.debug'):
            log_level = logging.DEBUG
        else:
            log_level = logging.DEBUG

        tl.set_log_level(log_level)

        if cgroup:
            _configure_service_cgroups(cgroup, root_cgroup)

    return run
