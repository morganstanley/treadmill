"""Master CLI plugin.
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import logging
import os
import time

import kazoo
import click

import pandas as pd
import tabulate

from treadmill import cli
from treadmill import context
from treadmill import plugin_manager
from treadmill import scheduler as treadmill_sched
from treadmill import reports
from treadmill.scheduler import loader
from treadmill.scheduler import master
from treadmill.scheduler import zkbackend
from treadmill.scheduler import fsbackend


_LOGGER = logging.getLogger(__name__)


def _print(frame, explain=False):
    """Print data frame based on cli options."""
    if cli.OUTPUT_FORMAT == 'csv':
        cli.out(frame.to_csv(index=False))
    elif cli.OUTPUT_FORMAT == 'json':
        cli.out(frame.to_json(orient='records'))
    elif cli.OUTPUT_FORMAT == 'yaml':
        fmt = plugin_manager.load('treadmill.formatters', 'yaml')
        cli.out(fmt.format(frame.to_dict(orient='records')))
    else:
        frame.replace(True, ' ', inplace=True)
        frame.replace(False, 'X', inplace=True)
        dict_ = frame.to_dict(orient='split')
        del dict_['index']
        cli.out(tabulate.tabulate(
            dict_['data'], dict_['columns'], tablefmt='simple'
        ))

        if explain:
            cli.echo_green(
                '\nX: designates the factor that prohibits scheduling '
                'the instance on the given server'
            )


def make_readonly_master(run_scheduler=False):
    """Prepare a readonly master."""
    treadmill_sched.DIMENSION_COUNT = 3

    backend = zkbackend.ZkReadonlyBackend(context.GLOBAL.zk.conn)

    # set timezone to master's
    data = backend.get('/')
    if data and 'timezone' in data:
        _LOGGER.debug('Setting timezone to %s', data['timezone'])
        os.environ['TZ'] = data['timezone']
        time.tzset()
    else:
        _LOGGER.warning('Missing timezone info.')

    cell_master = loader.Loader(
        backend,
        context.GLOBAL.cell
    )
    cell_master.load_model()

    if run_scheduler:
        cell_master.cell.schedule()

    return cell_master


def view_group(parent):
    """Scheduler CLI group."""
    # Disable too many branches warning.
    #
    # pylint: disable=R0912
    on_exceptions = cli.handle_exceptions([
        (kazoo.exceptions.NoAuthError, 'Error: not authorized.'),
        (kazoo.exceptions.NoNodeError, 'Error: resource does not exist.'),
        (context.ContextError, None),
    ])

    ctx = {
        'run_scheduler': False
    }

    @parent.group()
    @click.option('--reschedule', is_flag=True, default=False)
    @on_exceptions
    def view(reschedule):
        """Examine scheduler state."""
        ctx['run_scheduler'] = reschedule

    @view.command()
    @on_exceptions
    def servers():
        """View servers report"""
        cell_master = make_readonly_master(ctx['run_scheduler'])
        output = reports.servers(cell_master.cell, cell_master.trait_codes)
        output['valid_until'] = pd.to_datetime(output['valid_until'], unit='s')
        _print(output)

    @view.command()
    @click.option('--full', is_flag=True, default=False)
    @on_exceptions
    def apps(full):
        """View apps report"""
        cell_master = make_readonly_master(ctx['run_scheduler'])
        output = reports.apps(cell_master.cell, cell_master.trait_codes)
        # Replace integer N/As
        for col in ['identity', 'expires', 'lease', 'data_retention']:
            output.loc[output[col] == -1, col] = ''
        # Convert to datetimes
        for col in ['expires']:
            output[col] = pd.to_datetime(output[col], unit='s')
        # Convert to timedeltas
        for col in ['lease', 'data_retention']:
            output[col] = pd.to_timedelta(output[col], unit='s')
        # Float precision
        for col in ['util0', 'util1']:
            output[col] = output[col].map(lambda x: '%0.4f' % x)

        if not full:
            output = output[[
                'instance', 'allocation', 'partition', 'server',
                'mem', 'cpu', 'disk'
            ]]

        _print(output)

    @view.command()
    @on_exceptions
    def allocs():
        """View allocation report"""
        cell_master = make_readonly_master(ctx['run_scheduler'])
        allocs = reports.allocations(cell_master.cell, cell_master.trait_codes)
        _print(allocs)

    @view.command()
    @click.option('--histogram', is_flag=True, default=False,
                  help='Print histogram of reboot times')
    @on_exceptions
    def reboots(histogram):
        """View server reboot times."""
        cell_master = make_readonly_master(ctx['run_scheduler'])
        reboots = reports.reboots(cell_master.cell)
        if histogram:
            cli.out(reboots['valid-until'].value_counts().to_string())
        else:
            _print(reboots)

    del apps
    del servers
    del allocs
    del reboots


def explain_group(parent):
    """Scheduler explain CLI group."""

    @parent.group()
    def explain():
        """Explain scheduler internals.
        """

    @explain.command()
    @click.option('--instance', help='Application instance')
    @click.option('--partition', help='Cell partition', default='_default')
    @cli.admin.ON_EXCEPTIONS
    def queue(instance, partition):
        """Explain the application queue"""
        cell_master = make_readonly_master()
        frame = reports.explain_queue(cell_master.cell,
                                      partition,
                                      pattern=instance)
        _print(frame, explain=True)

    @explain.command()
    @click.argument('instance')
    @click.option('--mode', help='Tree traversal method',
                  type=click.Choice(reports.WALKS.keys()), default='default')
    @cli.admin.ON_EXCEPTIONS
    def placement(instance, mode):
        """Explain application placement"""
        cell_master = make_readonly_master()

        if instance not in cell_master.cell.apps:
            cli.bad_exit('Instance not found.')

        app = cell_master.cell.apps[instance]
        if app.server:
            cli.bad_exit('Instace already placed on %s' % app.server)

        frame = reports.explain_placement(cell_master.cell, app, mode)
        _print(frame, explain=True)

    del queue
    del placement


def snapshot_group(parent):
    """Scheduler snapshot CLI group."""

    @parent.group()
    def snapshot():
        """Snapshot scheduler state.
        """

    @snapshot.command()
    @click.option('--root', help='Output directory.',
                  required=True)
    @cli.admin.ON_EXCEPTIONS
    def take(root):
        """Take a snapshot of ZK state."""

        fsbackend.snapshot(context.GLOBAL.zk.conn, root)

    @snapshot.command()
    @click.option('--root', help='Output directory.',
                  required=True)
    @cli.admin.ON_EXCEPTIONS
    def run(root):
        """Run scheduler with fs backend."""
        treadmill_sched.DIMENSION_COUNT = 3

        cell_master = master.Master(
            fsbackend.FsBackend(root),
            context.GLOBAL.cell
        )
        cell_master.run_loop()

    del take
    del run


def init():
    """Return top level command handler."""

    @click.group()
    @click.option('--zookeeper', required=False,
                  envvar='TREADMILL_ZOOKEEPER',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    def top():
        """Report scheduler state.
        """

    view_group(top)
    explain_group(top)
    snapshot_group(top)
    return top
