# pylint: disable=C0103

"""Master CLI plugin."""


import click
import kazoo

import pandas as pd

from treadmill import cli
from treadmill import context
from treadmill import master
from treadmill import scheduler as treadmill_sched
from treadmill import reports


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

    do_reschedule = set()

    def _print_frame(output):
        """Prints dataframe."""
        pd.set_option('display.max_rows', None)
        if output is not None and len(output):
            if cli.OUTPUT_FORMAT == 'csv':
                print(output.to_csv())
            else:
                pd.set_option('expand_frame_repr', False)
                print(output)

    def _load():
        """Load cell information."""
        treadmill_sched.DIMENSION_COUNT = 3
        cell_master = master.Master(context.GLOBAL.zk.conn,
                                    context.GLOBAL.cell)
        cell_master.load_buckets()
        cell_master.load_cell()
        cell_master.load_servers(readonly=True)
        cell_master.load_allocations()
        cell_master.load_strategies()
        cell_master.load_apps(readonly=True)
        cell_master.load_identity_groups()
        cell_master.load_placement_data()

        if do_reschedule:
            cell_master.cell.schedule()

        return cell_master

    @parent.group()
    @click.option('--reschedule', is_flag=True, default=False)
    @on_exceptions
    def view(reschedule):
        """Examine scheduler state."""
        if reschedule:
            do_reschedule.add(1)

    @view.command()
    @click.option('--features/--no-features', is_flag=True, default=False)
    @on_exceptions
    def servers(features):
        """View servers report"""
        cell_master = _load()
        output = reports.servers(cell_master.cell)
        if features:
            feature_report = reports.node_features(cell_master.cell)
            _print_frame(pd.concat([output, feature_report], axis=1))
        else:
            _print_frame(output)

    @view.command()
    @on_exceptions
    def apps():
        """View apps report"""
        cell_master = _load()
        output = reports.apps(cell_master.cell)
        _print_frame(output)

    @view.command()
    @on_exceptions
    def allocs():
        """View allocation report"""
        cell_master = _load()
        allocs = reports.allocations(cell_master.cell)
        _print_frame(allocs)

    @view.command()
    @on_exceptions
    def queue():
        """View utilization queue"""
        cell_master = _load()
        apps = reports.apps(cell_master.cell)
        output = reports.utilization(None, apps)
        _print_frame(output)

    del apps
    del servers
    del allocs
    del queue


def init():
    """Return top level command handler."""

    @click.group()
    @click.option('--zookeeper', required=False,
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
    return top
