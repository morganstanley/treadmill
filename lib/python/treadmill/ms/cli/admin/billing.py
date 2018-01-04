"""Admin billing CLI module
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import logging
import os

import click
import dateutil.parser
import dateutil.relativedelta

# pylint: disable=E0611
from treadmill import billing
from treadmill import cli
from treadmill import context
from treadmill import fs


MONTH_START_BILLING = 15
MONTH_START_CALENDAR = 1
PREV_MONTH = -1
NEXT_MONTH = 1

_LOGGER = logging.getLogger(__name__)


def init():
    """Admin billing CLI module."""

    @click.group(name='billing')
    @click.option(
        '--progress', help='Show progress.',
        is_flag=True, default=False
    )
    def billing_grp(progress):
        """Billing utilities."""
        billing.INTERACTIVE = progress

    @billing_grp.command(name='cell')
    @click.option('--cell', help='Treadmill cell to report.',
                  envvar='TREADMILL_CELL', required=True,
                  expose_value=False, callback=cli.handle_context_opt)
    @click.option('--env', help='Treadmill reports environment.',
                  default='prod')
    @click.option('--out', '-o', help='Feed output file path.',
                  type=click.Path(), required=False)
    @click.option('--in', 'indir', help='Interval reports directory.',
                  type=click.Path())
    @click.option('--start', '-s', help='Start date (YYYY-MM-DD).',
                  required=True)
    @click.option('--end', '-e', help='End date (YYYY-MM-DD).', required=True)
    @click.option('--adjust/--no-adjust',
                  help='Adjust volumes to fit total cell volume.',
                  default=True)
    def cell_feed(env, out, indir, start, end, adjust):
        """Prepare the billing feed for a single cell."""
        start_dt = dateutil.parser.parse(start)
        end_dt = dateutil.parser.parse(end)

        cell = context.GLOBAL.cell

        start_ymd = start_dt.strftime('%Y-%m-%d')
        end_ymd = end_dt.strftime('%Y-%m-%d')
        _LOGGER.info(
            'Preparing %s billing report from %s to %s.',
            cell, start_ymd, end_ymd
        )

        if not out:
            outdir = billing.DAILY_DIR.format(env=env, cell=cell)
            fs.mkdir_safe(outdir)
            out = os.path.join(outdir, '{}_{}.csv'.format(start_ymd, end_ymd))
        if indir:
            billing.INTERVAL_DIR = indir

        volumes = billing.volumes_for_period(
            start_dt, end_dt, cell, env, adjust=adjust
        )

        _LOGGER.info('Writing billing report to %s.', out)
        volumes.to_csv(out, index=False)
        _LOGGER.info('Done.')

    @billing_grp.command(name='daily')
    @click.option('--cell', help='Treadmill cell to report.',
                  envvar='TREADMILL_CELL', required=True,
                  expose_value=False, callback=cli.handle_context_opt)
    @click.option('--env', help='Treadmill reports environment.',
                  default='prod')
    @click.option('--out', '-o', help='Feed output file path.',
                  type=click.Path())
    @click.option('--date', '-d', help='Date of the feed.')
    def daily_feed(env, out, date):
        """Prepare a daily billing feed for a cell."""
        if date:
            date_dt = dateutil.parser.parse(date)
            start_dt = date_dt.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_dt = start_dt + dateutil.relativedelta.relativedelta(days=1)
        else:
            # Compute yesterday's billing if no date provided
            now = datetime.datetime.utcnow()
            end_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start_dt = end_dt + dateutil.relativedelta.relativedelta(days=-1)

        cell = context.GLOBAL.cell

        start_ymd = start_dt.strftime('%Y-%m-%d')
        _LOGGER.info(
            'Preparing %s daily billing report for %s.', cell, start_ymd
        )

        if not out:
            outdir = billing.DAILY_DIR.format(env=env, cell=cell)
            fs.mkdir_safe(outdir)
            out = os.path.join(outdir, '{}.csv'.format(start_ymd))

        volumes = billing.volumes_for_period(
            start_dt, end_dt, cell, env,
            # Do not adjust volumes in daily feeds, they are adjusted by
            # billing.combine_periods in the monthly feed to better distribute
            # volumes between busy and quiet days
            adjust=False
        )

        _LOGGER.info('Writing daily billing report to %s.', out)
        volumes.to_csv(out, index=False)
        _LOGGER.info('Done.')

    @billing_grp.command(name='monthly')
    @click.option('--cell', help='Treadmill cell to report.',
                  envvar='TREADMILL_CELL', required=True,
                  expose_value=False, callback=cli.handle_context_opt)
    @click.option('--env', help='Treadmill reports environment.',
                  default='prod')
    @click.option('--out', '-o', help='Feed output file path.',
                  type=click.Path())
    @click.option('--in', 'indir', help='Daily feed directory.',
                  type=click.Path())
    @click.option('--month', '-m', help='Month of the feed (YYYY-MM).')
    def monthly_feed(env, out, indir, month):
        """Prepare a monthly billing feed for a cell."""
        if month:
            month_dt = dateutil.parser.parse(month).replace(
                # When parsing YYYY-MM, dateutil sets the day to current day
                day=MONTH_START_CALENDAR
            )
        else:
            # Prepare the current month if we're on or before the 15th,
            # otherwise it's the next month
            now = datetime.datetime.utcnow()
            month_dt = now.replace(
                day=MONTH_START_CALENDAR,
                hour=0, minute=0, second=0, microsecond=0
            )
            if now.day > MONTH_START_BILLING:
                month_dt += dateutil.relativedelta.relativedelta(
                    months=NEXT_MONTH
                )
        # A billing month goes from the 15th of the previous month to the
        # 15th of that month.
        start_dt = (
            month_dt + dateutil.relativedelta.relativedelta(months=PREV_MONTH)
        ).replace(day=MONTH_START_BILLING)
        end_dt = start_dt + dateutil.relativedelta.relativedelta(
            months=NEXT_MONTH
        )

        cell = context.GLOBAL.cell

        month_ym = end_dt.strftime('%Y-%m')
        _LOGGER.info(
            'Preparing %s monthly billing report for %s.', cell, month_ym
        )

        if not out:
            outdir = os.path.join(billing.MONTHLY_DIR.format(env=env), cell)
            fs.mkdir_safe(outdir)
            out = os.path.join(outdir, '{}.csv'.format(month_ym))
        if indir:
            billing.DAILY_DIR = indir

        volumes = billing.combine_periods(start_dt, end_dt, cell, env)
        if volumes is None:
            return

        _LOGGER.info('Writing monthly billing report to %s.', out)
        volumes.to_csv(out, index=False)
        _LOGGER.info('Done.')

    @billing_grp.command(name='compile')
    @click.option('--env', help='Treadmill reports environment.',
                  default='prod')
    @click.option('--out', '-o', help='Feed output file path.',
                  type=click.Path())
    @click.option('--in', 'indir', type=click.Path(),
                  help='Path to input dir with subdirs for each cell.')
    @click.option('--month', '-m', help='Month of the feed (YYYY-MM).')
    def compile_feeds(env, out, indir, month):
        """Compile the Treadmill feed from cell feeds."""
        if not month:
            # Prepare the current month if we're on or before the 15th,
            # otherwise it's the next month
            now = datetime.datetime.utcnow()
            month_dt = now.replace(
                day=MONTH_START_CALENDAR,
                hour=0, minute=0, second=0, microsecond=0
            )
            if now.day > MONTH_START_BILLING:
                month_dt += dateutil.relativedelta.relativedelta(
                    months=NEXT_MONTH
                )
            month = month_dt.strftime('%Y-%m')

        _LOGGER.info(
            'Preparing Treadmilly monthly billing report for %s.', month
        )

        if not out:
            outdir = billing.MONTHLY_DIR.format(env=env)
            fs.mkdir_safe(outdir)
            out = os.path.join(outdir, '{}.csv'.format(month))
        if indir:
            billing.MONTHLY_DIR = indir

        volumes = billing.concatenate_reports(month, env)

        _LOGGER.info('Writing Treadmill billing report to %s.', out)
        volumes.to_csv(out, index=False)
        _LOGGER.info('Done.')

    del cell_feed
    del compile_feeds
    del daily_feed
    del monthly_feed

    return billing_grp
