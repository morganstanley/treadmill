"""Implementation of scheduler reports API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import fnmatch
import logging
import time

import kazoo.exceptions

from treadmill import context
from treadmill import exc
from treadmill import reports
from treadmill import zknamespace as z
from treadmill import logcontext as lc

from treadmill import scheduler as tm_sched
from treadmill.scheduler import loader
from treadmill.scheduler import zkbackend

_LOGGER = logging.getLogger(__name__)
_CACHE_TIMEOUT = 180  # 3 mins
_LAST_CACHE_UPDATE = 0
_RO_SHEDULER_INSTANCE = None


def get_readonly_scheduler():
    """Prepare a readonly master."""
    # C0103(invalid-name): invalid variable name
    # W0603(global-statement): using the global statement
    # pylint: disable=C0103,W0603
    global _RO_SHEDULER_INSTANCE, _LAST_CACHE_UPDATE
    if (time.time() - _LAST_CACHE_UPDATE > _CACHE_TIMEOUT or
            not _RO_SHEDULER_INSTANCE):
        tm_sched.DIMENSION_COUNT = 3

        _RO_SHEDULER_INSTANCE = loader.Loader(
            zkbackend.ZkReadonlyBackend(context.GLOBAL.zk.conn),
            context.GLOBAL.cell
        )
        _RO_SHEDULER_INSTANCE.load_model()
        _LAST_CACHE_UPDATE = time.time()

    return _RO_SHEDULER_INSTANCE


def mk_explainapi():
    """API factory function returning _ExplainAPI class."""

    class _ExplainAPI:
        """API object implementing the scheduler explain functionality."""
        def __init__(self):
            self.get = _explain

    return _ExplainAPI


class API:
    """Scheduler reports API."""
    def __init__(self):

        def get(report_type, match=None, partition=None):
            """Fetch report from ZooKeeper and return it as a DataFrame."""
            try:
                data, _meta = context.GLOBAL.zk.conn.get(
                    z.path.state_report(report_type)
                )

                df = reports.deserialize_dataframe(data)
                if match:
                    df = _match_by_name(df, report_type, match)
                if partition:
                    df = _match_by_partition(df, partition)

                return df
            except kazoo.exceptions.NoNodeError:
                raise KeyError(report_type)

        self.get = get
        self.explain = mk_explainapi()()


def _match_by_name(dataframe, report_type, match):
    """Interpret match with report type and return resulting DataFrame.
    """
    pk_match = {
        'allocations': 'name',
        'apps': 'instance',
        'servers': 'name'
    }
    match = fnmatch.translate(match)
    subidx = dataframe[pk_match[report_type]].str.match(match)
    return dataframe.loc[subidx].reset_index(drop=True)


def _match_by_partition(dataframe, partition):
    """Filter out dataframes that don't match partition.
    """
    partition = fnmatch.translate(partition)
    subidx = dataframe['partition'].str.match(partition)
    return dataframe.loc[subidx].reset_index(drop=True)


def _explain(inst_id):
    """Explain application placement"""
    with lc.LogContext(_LOGGER, inst_id):
        start = time.time()
        ro_scheduler = get_readonly_scheduler()
        _LOGGER.info('ro_scheduler was ready in %s secs', time.time() - start)

        try:
            instance = ro_scheduler.cell.apps[inst_id]
        except KeyError:
            raise exc.NotFoundError(inst_id)

        if instance.server:
            raise exc.FoundError(
                'instance {} is already placed on {}'.format(
                    inst_id, instance.server
                )
            )

        return reports.explain_placement(
            ro_scheduler.cell, instance, 'servers'
        )
