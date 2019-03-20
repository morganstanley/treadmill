"""Implementation of treadmill admin ldap CLI direct plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import io
import os

import click
import ldif3

from treadmill import cli
from treadmill import context
from treadmill import fs


def init():
    """Direct ldap access CLI group.
    """

    @click.group()
    def direct():
        """Direct access to LDAP data.
        """

    @direct.command()
    @click.option('-a', '--attrs', help='Attributes',
                  type=cli.LIST, default=None)
    @click.argument('entry_dn')
    @cli.admin.ON_EXCEPTIONS
    def get(entry_dn, attrs):
        """Retreive a given entry in LDIF format.
        """
        entry_data = context.GLOBAL.admin.conn.get(
            entry_dn=entry_dn,
            attributes=attrs
        )
        if entry_data:
            cli.out(_sorted_ldif_entry(entry_dn, entry_data))

    @direct.command(name='set')
    @click.argument('ldif_file', type=click.File('rb'))
    @cli.admin.ON_EXCEPTIONS
    def set_(ldif_file):
        """Load DNs and attributes from a LDIF files and set them in LDAP.
        """
        # We need to strip all operational attributes before putting
        # the entry back into LDAP. We do this by retrieving and empty
        # DN and listing which attributes it has; they will be all
        # operational.
        empty_item = context.GLOBAL.admin.conn.get(
            entry_dn=None,
            attributes=['+']
        )
        operational_attributes = empty_item.keys()
        for entry_dn, entry_data in ldif3.LDIFParser(ldif_file).parse():
            cli.out('Loading %r', entry_dn)
            cleaned_data = {
                k: v
                for k, v in entry_data.items()
                if k not in operational_attributes
            }
            context.GLOBAL.admin.conn.set(
                entry_dn, cleaned_data
            )

    @direct.command(name='list')
    @click.option('--root', help='Search root.', default=None)
    @cli.admin.ON_EXCEPTIONS
    def list_(root):
        """List all defined DNs.
        """
        entry_dns = context.GLOBAL.admin.conn.list(root)
        for entry_dn in entry_dns:
            cli.out(entry_dn)

    @direct.command()
    @click.option('--root', help='Search root.')
    @click.option('-a', '--attrs', help='Attributes',
                  type=cli.LIST, default=None)
    @click.option('--output-dir', help='target output path.')
    @cli.admin.ON_EXCEPTIONS
    def dump(root, attrs, output_dir):
        """Dump all entries below a root as a tree of LDIF file
        """
        entries = context.GLOBAL.admin.conn.search(
            search_base=root,
            attributes=attrs,
        )
        for entry_dn, entry_data in entries:
            cli.out('dn: {dn}'.format(dn=entry_dn))
            _dump_entry(output_dir, entry_dn, entry_data)

    @direct.command()
    @cli.admin.ON_EXCEPTIONS
    @click.argument('entry_dn', required=True)
    def delete(entry_dn):
        """Delete LDAP object by DN.
        """
        context.GLOBAL.admin.conn.delete(entry_dn)

    del get
    del set_
    del delete
    del list_
    del dump

    return direct


def _sorted_ldif_entry(entry_dn, entry_data):
    """Generate a *sorted* version 1 LDIF entry.

    The goal is that each entry's attribute is in alphabetical ordered.
    Needed to have "stable" dumps, to be able to put them in version control.

    :returns:
        ``str`` - LDIFv1 representation of the entry.
    """
    # Make a sorted dictionary of key to list of utf8 encoded values
    prepared_data = collections.OrderedDict(
        [
            (
                key,
                [
                    datum.decode()
                    for datum in entry_data[key]
                ]
            )
            for key in sorted(entry_data.keys())
        ]
    )

    output_stream = io.BytesIO()
    writer = ldif3.LDIFWriter(output_stream, cols=78)
    writer.unparse(
        entry_dn, prepared_data
    )

    return output_stream.getvalue().decode()


def _dump_entry(base, entry_dn, entry_data):
    """Write an entry under a base directory.
    """
    subpath = ['data.ldif'] + entry_dn.split(',') + [base]
    fullpath = os.path.join(*reversed(subpath))
    fs.write_safe(
        fullpath,
        lambda fd: fd.write(_sorted_ldif_entry(entry_dn, entry_data)),
        mode='w',
        permission=0o644,
    )
