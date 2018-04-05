"""Treadmill cell checkout.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import logging
import sqlite3
import sys

import click
import pandas as pd

from treadmill import cli


_LOGGER = logging.getLogger(__name__)


def _print_query(conn, sql, index_col=None):
    """Print query results."""
    row_factory = conn.row_factory
    try:
        conn.row_factory = None
        frame = pd.read_sql(
            sql, conn, index_col=index_col
        )
        columns = {
            col: col.replace('_', '-')
            for col in frame.columns
        }
        frame.rename(columns=columns, inplace=True)
        if not frame.empty:
            pd.set_option('max_rows', None)
            pd.set_option('expand_frame_repr', False)
            print('---')
            print(frame)
            print('')

    finally:
        conn.row_factory = row_factory


def _print_check_result(description, data, status):
    """Print check result."""
    print(' {:.<69}  {}'.format(
        description.format(**data),
        status
    ))


def _run_check(conn, check, verbose, index_col):
    """Run check."""
    query = check['query']
    metric = check['metric']
    alerts = check.get('alerts', [])

    cursor = conn.execute(metric.format(query=query))
    check_failed = False
    empty = True
    for row in cursor:
        empty = False
        row = dict(zip(row.keys(), row))
        for alert in alerts:
            match = True
            status = 'pass'
            for key, prop_value in alert.get('match', {}).items():
                value = row.get(key)
                match = match and (value == prop_value)

            if not match:
                continue

            for key, limit in alert['threshold'].items():
                value = row.get(key)
                if value >= limit:
                    status = 'fail'
                    check_failed = True

            _print_check_result(
                alert['description'],
                row,
                status
            )

    if empty:
        for alert in alerts:
            _print_check_result(
                alert['description'],
                {},
                'pass'
            )

    # Alert will be triggerred, display the results thtat
    # caused the alert.
    if verbose >= 1 or check_failed:
        _print_query(
            conn,
            query,
            index_col=index_col
        )

    print('')


# pylint: disable=C0103
#
# pylint does not like 'db' as variable name.
def init():
    """Top level command handler."""

    @click.group(cls=cli.make_commands(__name__,
                                       chain=True,
                                       invoke_without_command=True))
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    @click.option('-v', '--verbose', count=True)
    @click.option('--db', help='Path to output sqlite db.')
    def run(verbose, db):
        """Run interactive checkout."""
        del verbose
        del db

    @run.resultcallback()
    def run_checkouts(checkouts, verbose, db):
        """Run interactive checkout."""
        # Too many nested blocks, need to refactor.
        #
        # pylint: disable=R1702
        common_args = {}

        if not db:
            db = ':memory:'
        conn = sqlite3.connect(db)

        for checkout in checkouts:
            try:
                metadata = checkout(conn=conn, **common_args)

                index_col = metadata.get('index')
                all_query = metadata['query']

                conn.commit()

                print(checkout.__doc__)

                if verbose >= 2:
                    _print_query(
                        conn,
                        all_query,
                        index_col=index_col
                    )

                row_factory = conn.row_factory
                conn.row_factory = sqlite3.Row

                for check in metadata.get('checks', []):
                    _run_check(conn, check, verbose, index_col)

            except Exception as err:  # pylint: disable=W0703
                _LOGGER.exception('%s', str(err))

    del run_checkouts
    return run
