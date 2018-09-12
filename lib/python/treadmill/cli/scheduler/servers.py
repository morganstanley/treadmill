"""Show servers report."""


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
    def servers(match, partition):
        """View servers report."""
        report = fetch_report('servers', match, partition)
        report['valid_until'] = pd.to_datetime(report['valid_until'], unit='s')
        print_report(report)

    return servers
