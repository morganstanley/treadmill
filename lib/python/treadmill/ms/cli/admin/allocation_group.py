"""This script is used to manage Treamdill allocation groups.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os

import click

from treadmill import cli

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import allocation_group


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
    """Archive command line handler."""
    formatter = cli.make_formatter(AllocationGroupPrettyFormatter)

    @click.group()
    def allocation_group_group():
        """Allocation group"""
        pass

    @allocation_group_group.command()
    @click.option('--eonid', help='System eon id.')
    @click.option('--environment', help='Allocation environment.')
    @click.argument('group', nargs=1, required=True)
    @cli.admin.ON_EXCEPTIONS
    def configure(group, eonid, environment):
        """Configure an allocation-group"""
        if eonid and environment:
            # check current user is treadmld/treadmlp as it will be
            # one of the owners, and allocation-groups must have one
            # of those as owner and no human owners
            if os.getenv('USER') not in ['treadmld', 'treadmlp']:
                cli.bad_exit('Error: Must run as treadmld/treadmlp')

            allocation_group.create(group, eonid, environment)

        grp = allocation_group.get(group)
        cli.out(formatter(grp))

    @allocation_group_group.command()
    @click.argument('group', nargs=1, required=True)
    @cli.admin.ON_EXCEPTIONS
    def delete(group):
        """Configure an allocation-group"""
        allocation_group.delete(group)

    @allocation_group_group.command()
    @click.option('--admins', help='Membership admins.', type=cli.LIST)
    @click.argument('group', nargs=1, required=True)
    @cli.admin.ON_EXCEPTIONS
    def insert(group, admins):
        """Configure an allocation-group"""
        allocation_group.insert(group, admins)

    @allocation_group_group.command()
    @click.option('--admins', help='Membership admins.', type=cli.LIST)
    @click.argument('group', nargs=1, required=True)
    @cli.admin.ON_EXCEPTIONS
    def remove(group, admins):
        """Configure an allocation-group"""
        allocation_group.remove(group, admins)

    del configure
    del delete
    del insert
    del remove

    return allocation_group_group
