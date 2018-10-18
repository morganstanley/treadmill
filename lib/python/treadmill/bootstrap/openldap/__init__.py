"""Treadmill openldap bootstrap.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from .. import aliases

DEFAULTS = {
    'dir_config': '{{ dir }}/etc/openldap',
    'dir_schema': '{{ dir_config }}/schema',
    'attribute_options': ['tm-'],
    'backends': [
        {
            'name': '{0}config',
            'owner': '{{ owner }}',
            'rootdn': 'cn=Manager,cn=config',
            'rootpw': '{{ rootpw }}',
            'suffix': 'cn=config',
            'syncrepl_searchbase': 'cn=treadmill,cn=schema,cn=config',
        },
        {
            'name': '{1}mdb',
            'objectclass': 'olcMdbConfig',
            'owner': '{{ owner }}',
            'rootdn': 'cn=Manager,{{ suffix }}',
            'rootpw': '{{ rootpw }}',
            'suffix': '{{ suffix }}',
            'syncrepl_searchbase': '{{ suffix }}',
            'index': {
                'objectClass': 'eq',
                'entryCSN': 'eq',
            },
        },
    ],
    'log_levels': [16384],
    'schemas': ['file://{{ openldap }}/etc/openldap/schema/core.ldif']
}

ALIASES = aliases.ALIASES
