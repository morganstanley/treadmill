"""Show apps report."""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click
import pandas as pd

from treadmill import cli
from treadmill.cli.scheduler import fetch_report, print_report
from treadmill import restclient


def init():
    """Return top level command handler."""

    @click.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Server name pattern match')
    @click.option('--partition', help='Partition name pattern match')
    @click.option('--full', is_flag=True, default=False)
    def apps(match, partition, full):
        """View apps report."""
        report = fetch_report('apps', match, partition)
        # Replace integer N/As
        for col in ['identity', 'expires', 'lease', 'data_retention']:
            report.loc[report[col] == -1, col] = ''
        # Convert to datetimes
        for col in ['expires']:
            report[col] = pd.to_datetime(report[col], unit='s')
        # Convert to timedeltas
        for col in ['lease', 'data_retention']:
            report[col] = pd.to_timedelta(report[col], unit='s')
        report = report.fillna('')

        if not full:
            report = report[[
                'instance', 'allocation', 'partition', 'server',
                'mem', 'cpu', 'disk'
            ]]

        print_report(report)

    return apps
