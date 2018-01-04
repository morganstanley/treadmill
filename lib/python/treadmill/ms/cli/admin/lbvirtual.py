"""Admin CLI to make low level changes to LB virtuals"""


from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from __future__ import absolute_import

import logging
import re

import click

from treadmill import cli
from treadmill.formatter import tablefmt

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import lbcontrol
from treadmill.ms import lbendpoint

_LOGGER = logging.getLogger(__name__)


class LBVirtualPrettyFormatter(object):
    """Pretty table LBVirtual formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        template_tbl = tablefmt.make_dict_to_table([
            ('name', None, None),
            ('version', None, None),
        ])
        list_schema = [('name', None, None)]
        schema = [('name', None, None),
                  ('port', None, None),
                  ('connection timeout', 'conntimeout', None),
                  ('persist type', 'persisttype', None),
                  ('persist timeout', 'persisttimeout', None),
                  ('template', None, template_tbl)]

        format_item = tablefmt.make_dict_to_table(schema)
        format_list = tablefmt.make_list_to_table(list_schema)

        if isinstance(item, list):
            return format_list(item)

        return format_item(item)


def _virtual_sum_obj2virtual_sum(virtual_sum_obj):
    """VirtualSummary SOAP object to virtual dict"""
    # disable complaints about accessing protected members
    # pylint: disable=W0212
    virt_sum = dict(name=virtual_sum_obj._name,
                    cluster=virtual_sum_obj._cluster,)

    return virt_sum


def _virtual_obj2virtual(virtual_obj):
    """Virtual SOAP object to virtual dict"""
    # disable complaints about accessing protected members
    # pylint: disable=W0212
    virtual = dict(name=virtual_obj._name,
                   port=virtual_obj._port,
                   prodstatus=getattr(virtual_obj, '_prodstatus', None),
                   conntimeout=getattr(virtual_obj, '_conntimeout', None),
                   persisttype=getattr(virtual_obj, '_persisttype', None),
                   persisttimeout=getattr(virtual_obj, '_persisttimeout',
                                          None),
                   template=dict(name=virtual_obj.template._name,
                                 version=virtual_obj.template._version))
    return virtual


def _validate_virt_name(name):
    """Check that the specified virtual complies with the naming convention"""
    if not re.match(lbendpoint.VIRTUAL_NAME_REGEX, name):
        cli.bad_exit('Virtual name must match REGEX %s',
                     lbendpoint.VIRTUAL_NAME_REGEX)


def init():
    """Initiliaze LB virtual"""
    formatter = cli.make_formatter('ms-lbvirtual')
    ctx = {
        'lbc': None
    }

    @click.group()
    @click.option('--lbenv', help='LB Environment',
                  default='prod')
    def lbvirtual(lbenv):
        """Manage LB virtuals"""
        ctx['lbc'] = lbcontrol.LBControl2(lbenv)

    @lbvirtual.command()
    @click.argument('name')
    @click.option('--port', required=True,
                  help='Desired port; only admin can supply', type=int)
    @click.option('--prodstatus', required=True,
                  help='Desired prodstatus; only admin can supply',
                  type=click.Choice(['prod', 'uat', 'qa', 'dev']))
    @cli.admin.ON_EXCEPTIONS
    def configure(name, port, prodstatus):
        """Configure lbvirtual"""
        lbc = ctx['lbc']

        _validate_virt_name(name)

        vip0 = re.sub(r'\.\d+$', '', name)

        virtual = lbc.get_virtual(name, raw=True)

        if virtual:
            cli.out(formatter(_virtual_obj2virtual(virtual)))
            return

        lbendpoint.create_lbendpoint_virtual(lbc, vip0, port, prodstatus)

        virtual = lbc.get_virtual(name, raw=True)
        _LOGGER.debug('virtual: %r', virtual)
        cli.out(formatter(_virtual_obj2virtual(virtual)))

    @lbvirtual.command()
    @click.argument('name')
    def delete(name):
        """Delete an LB virtual"""
        lbc = ctx['lbc']
        _validate_virt_name(name)
        virtual = lbc.get_virtual(name, raw=True)
        if not virtual:
            cli.bad_exit('Virtual %s does not exist' % name)

        lbc.delete_virtual(name)

    @lbvirtual.command(name='list')
    @click.option('--search', help='The "fuzzy" search')
    def _list(search):
        """List all LB virtuals"""
        if not search:
            search = lbendpoint.DEFAULT_VIRTUAL_SEARCH_STR.format('%')

        lbc = ctx['lbc']
        res = lbc.list_virtuals(search, raw=True)
        _LOGGER.debug(res)

        virt_sums = [_virtual_sum_obj2virtual_sum(virt_sum_obj)
                     for virt_sum_obj in res]
        _LOGGER.debug('virtualsummary: %r', virt_sums)

        cli.out(formatter(virt_sums))

    @lbvirtual.command()
    @click.argument('name')
    @click.option('-conn-to', '--conn-timeout', help='Connection idle timeout',
                  type=int)
    @click.option('-pers', '--persist-type', help='Persist type',
                  type=click.Choice(['none', 'cookie', 'ssl', 'source_addr',
                                     'dest_addr']))
    @click.option('-pers-to', '--persist-timeout', help='Persist timeout',
                  type=int)
    @click.option('--prodstatus',
                  help='Desired prodstatus; only admin can supply',
                  type=click.Choice(['prod', 'uat', 'qa', 'dev']))
    @cli.admin.ON_EXCEPTIONS
    def update(name, conn_timeout, persist_type, persist_timeout, prodstatus):
        """Update lbvirtual"""
        lbc = ctx['lbc']
        _validate_virt_name(name)

        virtual = {}
        if conn_timeout:
            virtual['_conntimeout'] = conn_timeout
        if persist_type:
            virtual['_persisttype'] = persist_type
        if persist_timeout:
            virtual['_persisttimeout'] = persist_timeout
        if prodstatus:
            # pylint: disable=unsubscriptable-object
            virtual['_prodstatus'] = lbcontrol.ProdStatus[prodstatus].value

        if virtual:
            virtual = lbc.update_virtual(name, virtual, raw=True)
            cli.out(formatter(_virtual_obj2virtual(virtual)))

    @lbvirtual.command()
    @click.argument('name')
    def push(name):
        """Push lbvirtual."""
        lbc = ctx['lbc']
        _validate_virt_name(name)

        lbc.push_virtual(lbvirtual)

    del configure
    del delete
    del _list
    del update
    del push

    return lbvirtual
