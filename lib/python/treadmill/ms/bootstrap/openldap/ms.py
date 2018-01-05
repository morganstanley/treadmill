"""MS defaults."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from treadmill import sysinfo

from .. import ms_aliases as aliases

DEFAULTS = {
    'dir_config': '{{ dir }}/etc/openldap',
    'dir_schema': '{{ dir_config }}/schema',
    'host': sysinfo.hostname(),
    'local': {'rootcn': 'Manager'},
    'attribute_options': ['tm-'],
    'backends': [{'gssapi': 1,
                  'name': '{0}config',
                  'owner': '{{ treadmillid }}',
                  'rootdn': 'cn={{local.rootcn}},cn=config',
                  'rootpw': None,
                  'maxsize': None,
                  'suffix': 'cn=config'},
                 {'gssapi': 1,
                  'name': '{1}mdb',
                  'objectclass': 'olcMdbConfig',
                  'owner': '{{ treadmillid }}',
                  'rootdn': 'cn={{local.rootcn}},dc=ms,dc=com',
                  'rootpw': None,
                  # This is 10GB, which should be good for a LONG time
                  'maxsize': '10294967296',
                  'suffix': 'dc=ms,dc=com'}],
    'log_levels': [16384],
    'schemas': ['file://{{ openldap }}/etc/openldap/schema/core.ldif']
}

ALIASES = aliases.ALIASES
