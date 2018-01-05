"""Instance plugin.

Adds proid and environment attributes from the proiddb.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

from treadmill import admin

from treadmill.ms import msdependencies  # pylint: disable=unused-import

from treadmill.ms import proiddb


_LOGGER = logging.getLogger(__name__)

_ACCEPTABLE_ENVS = ['dev', 'qa', 'uat', 'prod']

FWD_PROD_HOST = 'fwldap-prod.ms.com:389'

_FWD_LDAP = None


def _prepare_fwd_connection():
    """Connect to the Firmwide Directory LDAP."""
    global _FWD_LDAP  # Accept globals - pylint: disable=W0603
    if not _FWD_LDAP:
        _FWD_LDAP = admin.Admin(FWD_PROD_HOST, '')
        _FWD_LDAP.connect()


def _personal_container(address):
    """Fetch info for a user@group address."""
    _prepare_fwd_connection()

    user, group = address.split('@', 1)

    # The validity of user and group are ensured by the PGE policy

    fwd_group = _FWD_LDAP.get(
        'cn={},ou=Groups,o=Morgan Stanley'.format(group),
        '(objectclass=msaclgroup)',
        ['msenvironment'],
        paged_search=False
    )

    env = next(
        env.lower()
        for env in fwd_group.get('msenvironment', [])
        if env.lower() in _ACCEPTABLE_ENVS
    )

    return user, env


def _default_affinity(rsrc_id):
    """Return default affinity based on rsrc id.

    Affinity is calculated as <proid or group>.<first component>
    """
    if '@' in rsrc_id:
        return '{0}.{1}'.format(*rsrc_id[rsrc_id.find('@') + 1:].split('.'))
    else:
        return '{0}.{1}'.format(*rsrc_id.split('.'))


def add_attributes(rsrc_id, manifest):
    """Add additional attributes to the manifest."""
    component = rsrc_id[0:rsrc_id.find('.')]
    if '@' in component:
        # component is in the form <user>@<group>
        _LOGGER.info('Processing personal container: %s', component)
        user, env = _personal_container(component)
        updated = {
            'proid': user,
            'environment': env
        }
    else:
        # component is a proid
        updated = {
            'proid': component,
            'environment': proiddb.environment(component),
        }

    if manifest.get('affinity') is None:
        updated['affinity'] = _default_affinity(rsrc_id)

    _LOGGER.info('Adding attributes: %r', updated)

    updated.update(manifest)
    return updated


def remove_attributes(manifest):
    """Removes extra attributes from the manifest."""
    if 'proid' in manifest:
        del manifest['proid']
    if 'environment' in manifest:
        del manifest['environment']

    return manifest
