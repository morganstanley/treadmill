"""Show apps report."""


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import click

from treadmill import cli
from treadmill.cli.scheduler import fetch_report, print_report
from treadmill import restclient


def init():
    """Return top level command handler."""

    @click.command()
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    @click.option('--match', help='Server name pattern match')
    @click.option('--partition', help='Partition name pattern match')
    def allocs(match, partition):
        """View allocations report."""
        report = fetch_report(
            'allocations', match, partition
        )
        report = report.loc[
            ~report.name.str.startswith('_default/')
        ].reset_index(drop=True)
        print_report(report)

    return allocs
