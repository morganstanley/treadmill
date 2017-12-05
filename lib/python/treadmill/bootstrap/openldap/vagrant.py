"""Vagrant specific install profile."""

from .. import vagrant_aliases as aliases

DEFAULTS = {
    'schemas': ['file:///etc/openldap/schema/core.ldif']
}

ALIASES = aliases.ALIASES
