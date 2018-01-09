"""Top level command for Treadmill reports.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json

import click
import pandas as pd
import tabulate

from six.moves import urllib_parse

from treadmill import cli
from treadmill import context
from treadmill import plugin_manager
from treadmill import restclient


def fetch_report(cell_api, report_type, match=None, partition=None):
    """Fetch a report of the given type and return it as a DataFrame."""
    api_urls = context.GLOBAL.cell_api(cell_api)
    path = '/scheduler/{}'.format(report_type)

    query = {}
    if match:
        query['match'] = match
    if partition:
        query['partition'] = partition

    if query:
        path += '?' + urllib_parse.urlencode(query)

    response = restclient.get(api_urls, path).json()
    return pd.DataFrame(response['data'], columns=response['columns'])


def print_report(frame):
    """Pretty-print the report."""
    if cli.OUTPUT_FORMAT is None:
        frame.replace(True, ' ', inplace=True)
        frame.replace(False, 'X', inplace=True)
        dict_ = frame.to_dict(orient='split')
        del dict_['index']

        cli.out(
            tabulate.tabulate(
                dict_['data'], dict_['columns'], tablefmt='simple'
            )
        )
        cli.echo_green('\nX: designates the factor that prohibits scheduling '
                       'the instance on the given server')
    elif cli.OUTPUT_FORMAT == 'yaml':
        fmt = plugin_manager.load('treadmill.formatters', 'yaml')
        cli.out(fmt.format(frame.to_dict(orient='records')))
    elif cli.OUTPUT_FORMAT == 'json':
        cli.out(frame.to_json(orient='records'))
    elif cli.OUTPUT_FORMAT == 'csv':
        cli.out(frame.to_csv(index=False))
    else:
        cli.out(tabulate.tabulate(frame, frame.columns, tablefmt='simple'))


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
