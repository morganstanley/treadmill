"""Implementation of treadmill-admin CLI plugin."""


import logging
import logging.config
import os
import tempfile
import traceback

import click
import yaml

import treadmill
from treadmill import cli
from .. import cgroups


def _configure_core_cgroups(service_name):
    """Configure service specific cgroups."""
    group = os.path.join('treadmill/core', service_name)
    for subsystem in ['memory', 'cpu', 'cpuacct', 'blkio']:
        logging.info('creating and joining: %s/%s', subsystem, group)
        cgroups.create(subsystem, group)
        cgroups.join(subsystem, group)

    memlimits = ['memory.limit_in_bytes',
                 'memory.memsw.limit_in_bytes',
                 'memory.soft_limit_in_bytes']
    for limit in memlimits:
        parent_limit = cgroups.get_value('memory', 'treadmill/core', limit)
        logging.info('setting %s: %s', limit, parent_limit)
        cgroups.set_value('memory', group, limit, parent_limit)

    cpulimits = ['cpu.shares']
    for limit in cpulimits:
        parent_limit = cgroups.get_value('cpu', 'treadmill/core', limit)
        logging.info('setting %s: %s', limit, parent_limit)
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
        # Default logging to cli.yml, at CRITICAL, unless --debug
        log_conf_file = os.path.join(treadmill.TREADMILL, 'etc', 'logging',
                                     'daemon.yml')
        try:
            with open(log_conf_file, 'r') as fh:
                log_config = yaml.load(fh)
                logging.config.dictConfig(log_config)

        except IOError:
            with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
                traceback.print_exc(file=f)
                click.echo('Unable to load log conf: %s [ %s ]' %
                           (log_conf_file, f.name), err=True)

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
