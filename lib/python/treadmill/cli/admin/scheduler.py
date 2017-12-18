"""Master CLI plugin.
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import logging

import click
import kazoo

import pandas as pd

from treadmill import cli
from treadmill import context
from treadmill import scheduler as treadmill_sched
from treadmill import reports
from treadmill.scheduler import loader
from treadmill.scheduler import zkbackend


_LOGGER = logging.getLogger(__name__)


def make_readonly_master(run_scheduler=False):
    """Prepare a readonly master."""
    treadmill_sched.DIMENSION_COUNT = 3

    cell_master = loader.Loader(
        zkbackend.ZkReadonlyBackend(context.GLOBAL.zk.conn),
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

    def _print_frame(output):
        """Print dataframe."""
        pd.set_option('display.max_rows', None)
        if output is not None and len(output):
            if cli.OUTPUT_FORMAT == 'csv':
                print(output.to_csv())
            else:
                pd.set_option('expand_frame_repr', False)
                output.replace(True, ' ', inplace=True)
                output.replace(False, 'X', inplace=True)
                print(output)

    @parent.group()
    @click.option('--reschedule', is_flag=True, default=False)
    @on_exceptions
    def view(reschedule):
        """Examine scheduler state."""
        ctx['run_scheduler'] = reschedule

    @view.command()
    @click.option('--features/--no-features', is_flag=True, default=False)
    @on_exceptions
    def servers(features):
        """View servers report"""
        cell_master = make_readonly_master(ctx['run_scheduler'])
        output = reports.servers(cell_master.cell)
        output['valid_until'] = pd.to_datetime(output['valid_until'], unit='s')
        if features:
            feature_report = reports.node_features(cell_master.cell)
            _print_frame(pd.concat([output, feature_report], axis=1))
        else:
            _print_frame(output)

    @view.command()
    @on_exceptions
    def apps():
        """View apps report"""
        cell_master = make_readonly_master(ctx['run_scheduler'])
        output = reports.apps(cell_master.cell)
        # Replace integer N/As
        for col in ['identity', 'expires', 'lease', 'data_retention']:
            output.loc[output[col] == -1, col] = ''
        # Convert to datetimes
        for col in ['expires']:
            output[col] = pd.to_datetime(output[col], unit='s')
        # Convert to timedeltas
        for col in ['lease', 'data_retention']:
            output[col] = pd.to_timedelta(output[col], unit='s')
        _print_frame(output.fillna(''))

    @view.command()
    @on_exceptions
    def allocs():
        """View allocation report"""
        cell_master = make_readonly_master(ctx['run_scheduler'])
        allocs = reports.allocations(cell_master.cell)
        _print_frame(allocs)

    @view.command()
    @on_exceptions
    def queue():
        """View utilization queue"""
        cell_master = make_readonly_master(ctx['run_scheduler'])
        apps = reports.apps(cell_master.cell)
        output = reports.utilization(None, apps)
        _print_frame(output)

    @view.command()
    @click.option('--histogram', is_flag=True, default=False,
                  help='Print histogram of reboot times')
    @on_exceptions
    def reboots(histogram):
        """View server reboot times."""
        cell_master = make_readonly_master(ctx['run_scheduler'])
        reboots = reports.reboots(cell_master.cell)
        if histogram:
            print(reboots['valid-until'].value_counts().to_string())
        else:
            _print_frame(reboots)

    del apps
    del servers
    del allocs
    del queue
    del reboots


def explain_group(parent):
    """Scheduler explain CLI group."""

    def _print_frame(df):
        """Prints dataframe."""
        if not df.empty:
            pd.set_option('display.max_rows', None)
            pd.set_option('float_format', lambda f: '%f' % f)
            pd.set_option('expand_frame_repr', False)
            print(df.to_string(index=False))

    @parent.group()
    def explain():
        """Explain scheduler internals"""
        pass

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
        _print_frame(frame)

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
        _print_frame(frame)

    del queue
    del placement


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
        """Report scheduler state."""
        pass

    view_group(top)
    explain_group(top)
    return top
