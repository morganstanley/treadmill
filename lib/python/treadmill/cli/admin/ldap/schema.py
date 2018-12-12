"""Implementation of treadmill admin ldap CLI schema plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import codecs

import click
import pkg_resources
import six

from treadmill import cli
from treadmill import context
from treadmill import yamlwrapper as yaml


def init():
    """Schema CLI group"""

    formatter = cli.make_formatter('ldap-schema')

    @click.command(name='schema')
    @click.option('-u', '--update', help='Refresh LDAP schema.', is_flag=True,
                  default=False)
    @cli.admin.ON_EXCEPTIONS
    def _schema(update):
        """View or update LDAP schema"""
        if update:
            context.GLOBAL.ldap.user = 'cn=Manager,cn=config'

            utf8_reader = codecs.getreader('utf8')
            schema_rsrc = utf8_reader(
                pkg_resources.resource_stream('treadmill',
                                              '/etc/ldap/schema.yml')
            )

            schema = yaml.load(stream=schema_rsrc)
            context.GLOBAL.admin.conn.update_schema(schema)

        schema_obj = context.GLOBAL.admin.conn.schema()

        def dict_to_namevalue_list(item):
            """Translates name: value dict into [{name: $name, ...}]
            """
            result = []
            for pair in sorted(six.iteritems(item)):
                entry = pair[1].copy()
                entry.update(
                    {'name': pair[0]}
                )
                result.append(entry)

            return result

        schema_obj['attributeTypes'] = dict_to_namevalue_list(
            schema_obj['attributeTypes'])
        schema_obj['objectClasses'] = dict_to_namevalue_list(
            schema_obj['objectClasses'])

        cli.out(formatter(schema_obj))

    return _schema
