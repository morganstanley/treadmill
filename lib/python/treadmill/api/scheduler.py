"""Implementation of scheduler reports API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import fnmatch

import kazoo.exceptions

from treadmill import context
from treadmill import reports
from treadmill import zknamespace as z


class API(object):
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
