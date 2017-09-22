"""Top level command for Treadmill reports.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import pkgutil
import urllib

import click
import pandas as pd
import tabulate

from treadmill import cli
from treadmill import context
from treadmill import restclient


__path__ = pkgutil.extend_path(__path__, __name__)


def fetch_report(cell_api, report_type, match=None):
    """Fetch a report of the given type and return it as a DataFrame."""
    api_urls = context.GLOBAL.cell_api(cell_api)
    path = '/scheduler/{}'.format(report_type)

    query = {}
    if match:
        query['match'] = match
    if query:
        path += '?' + urllib.urlencode(query)

    response = restclient.get(api_urls, path).json()
    return pd.DataFrame(response['data'], columns=response['columns'])


def print_report(frame):
    """Pretty-print the report."""
    print(tabulate.tabulate(frame, frame.columns, tablefmt='simple'))


def init():
    """Return top level command handler."""

    @click.group(cls=cli.make_commands(__name__))
    @click.option(
        '--cell',
        help='Treadmill cell',
        envvar='TREADMILL_CELL',
        callback=cli.handle_context_opt,
        expose_value=False,
        required=True
    )
    @click.option(
        '--api',
        help='Cell API URL',
        metavar='URL',
        envvar='TREADMILL_CELLAPI'
    )
    @click.pass_context
    def run(ctx, api):
        """Report scheduler state."""
        if not ctx.obj:
            ctx.obj = {}  # Doesn't seem to exist in testing
        ctx.obj['api'] = api

    return run
