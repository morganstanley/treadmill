"""Admin CLI to make low level changes to LB pools
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import re

import click

from treadmill import cli
from treadmill.formatter import tablefmt

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import lbcontrol
from treadmill.ms import lbendpoint


_LOGGER = logging.getLogger(__name__)


class LBPoolPrettyFormatter(object):
    """Pretty table LBPool formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        members_tbl = tablefmt.make_list_to_table([
            ('name', None, None),
            ('port', None, None),
        ])
        list_schema = [('name', None, None)]
        schema = [('name', None, None),
                  ('members', None, members_tbl)]

        format_item = tablefmt.make_dict_to_table(schema)
        format_list = tablefmt.make_list_to_table(list_schema)

        if isinstance(item, list):
            return format_list(item)

        return format_item(item)


def _pool_obj2pool(pool_obj):
    """Pool SOAP object to pool dict"""
    # Disable W0212P: Access to protected member
    # pylint: disable=W0212
    pool = dict(name=pool_obj._name)
    members = [dict(name=pm.service._name, port=pm.service._port)
               for pm in pool_obj.members]
    pool['members'] = members
    return pool


def init():
    """Initiliaze LB pool"""
    formatter = cli.make_formatter('ms-lbpool')
    ctx = {
        'lbc': None
    }

    @click.group()
    @click.option('--lbenv', help='LB Control Environment',
                  default='prod')
    def lbpool(lbenv):
        """Manage LB pools"""
        ctx['lbc'] = lbcontrol.LBControl2(lbenv)

    @lbpool.command()
    @click.argument('name')
    @cli.admin.ON_EXCEPTIONS
    def configure(name):
        """Configure lbpool"""
        lbc = ctx['lbc']

        if not re.match(lbendpoint.POOL_NAME_REGEX, name):
            cli.bad_exit('Pool name must match REGEX %s',
                         lbendpoint.POOL_NAME_REGEX)

        pool = lbc.get_pool(name, raw=True)
        if pool:
            cli.out(formatter(_pool_obj2pool(pool)))
            return

        lbendpoint.create_pool(lbc, name)

        pool = lbc.get_pool(name, raw=True)
        cli.out(formatter(_pool_obj2pool(pool)))

    @lbpool.command()
    @click.argument('name')
    def delete(name):
        """Delete an LB pool"""
        lbc = ctx['lbc']
        pool = lbc.get_pool(name, raw=True)
        if not pool:
            cli.bad_exit('Pool %s does not exist' % name)

        lbc.delete_pool(name)

    @lbpool.command(name='list')
    @click.option('--search', help='The "fuzzy" search')
    def _list(search):
        """List all LB pools"""
        if not search:
            search = lbendpoint.DEFAULT_POOL_SEARCH_STR.format('%')

        lbc = ctx['lbc']
        res = lbc.list_pools(search)

        pools = [_pool_obj2pool(pool_obj) for pool_obj in res]
        _LOGGER.debug('pools: %r', pools)

        cli.out(formatter(pools))

    del configure
    del delete
    del _list

    return lbpool
