"""Treadmill Allocation-group CLI.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import click

from treadmill import cli
from treadmill import context
from treadmill import restclient

_LOGGER = logging.getLogger(__name__)

_REST_PATH = '/allocation-group/'


class AllocationGroupPrettyFormatter(object):
    """Pretty table Allocation Group formatter."""

    @staticmethod
    def format(item):
        """Return pretty-formatted item."""
        schema = [('name', None, None),
                  ('eonid', None, None),
                  ('environment', None, None),
                  ('owners', None, '\n'.join),
                  ('admins', None, '\n'.join)]

        format_item = cli.make_dict_to_table(schema)
        return format_item(item)


def init():
    """Configures Allocation-group"""
    formatter = cli.make_formatter(AllocationGroupPrettyFormatter)
    ctx = {}

    @click.group(name='allocation-group')
    @click.option('--api', help='API url to use.',
                  metavar='URL',
                  envvar='TREADMILL_RESTAPI')
    def allocgroup(api):
        """Manage Treadmill Allocation-group configuration"""
        ctx['api'] = api

    @allocgroup.command()
    @click.argument('group', nargs=1, required=True)
    @click.option('--eonid', help='Eonid', type=int)
    @click.option('--environment', help='Environment')
    @click.option('--admins', help='Membership admins', type=cli.LIST)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def configure(group, eonid, environment, admins):
        """Create, modify or get Treadmill Allocation-group entry"""
        restapi = context.GLOBAL.admin_api(ctx['api'])
        url = _REST_PATH + group
        data = {}

        if eonid:
            data['eonid'] = eonid
        if environment:
            data['environment'] = environment
        if admins:
            data['admins'] = admins

        if eonid and environment:
            _LOGGER.debug('Trying to create allocation-group %s', group)
            restclient.post(restapi, url, data)
        elif admins:
            _LOGGER.debug('Updating allocation-group %s', group)
            restclient.put(restapi, url, data)

        _LOGGER.debug('Retrieving allocation-group %s', group)
        entry = restclient.get(restapi, url).json()

        cli.out(formatter(entry))

    @allocgroup.command()
    @click.argument('group', nargs=1, required=True)
    @cli.handle_exceptions(restclient.CLI_REST_EXCEPTIONS)
    def delete(group):
        """Delete Treadmill Allocation-group"""
        restapi = context.GLOBAL.admin_api(ctx['api'])
        url = _REST_PATH + group
        restclient.delete(restapi, url)

    del delete
    del configure

    return allocgroup
