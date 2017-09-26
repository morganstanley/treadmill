"""Implementation of scheduler reports API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import fnmatch
import io

import kazoo
import pandas as pd

from treadmill import authz
from treadmill import context
from treadmill import zknamespace as z


class API(object):
    """Scheduler reports API."""
    def __init__(self):

        def get(report_type, match=None):
            """Fetch report from ZooKeeper and return it as a DataFrame."""
            try:
                data, _meta = context.GLOBAL.zk.conn.get(
                    z.path.state_report(report_type)
                )

                csv = io.StringIO(data.decode())
                df = pd.read_csv(csv)
                if match:
                    df = _match_by_name(match, report_type, df)

                return df
            except kazoo.exceptions.NoNodeError:
                raise KeyError(report_type)

        self.get = get


def _match_by_name(match, report_type, dataframe):
    """
    Interpret match with report type and return resulting DataFrame.
    """
    pk_match = {
        'allocations': 'name',
        'apps': 'instance',
        'servers': 'name'
    }
    match = fnmatch.translate(match)
    subidx = dataframe[pk_match[report_type]].str.match(match)
    return dataframe.loc[subidx].reset_index(drop=True)


def init(authorizer):
    """Returns module API wrapped with authorizer function."""
    api = API()
    return authz.wrap(api, authorizer)
