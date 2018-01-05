"""Treadmill Allocation Groups.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging
import os

import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

from treadmill import admin
from treadmill import exc


_LOGGER = logging.getLogger(__name__)

_MADMIN = '/ms/dist/aurora/bin/madmin'

_DESC = 'Treadmill ldap allocation'
_FWD_PROD_HOST = 'fwldap-prod.ms.com:389'


def get(group):
    """Get allocation group details"""
    ldap = admin.Admin([_FWD_PROD_HOST], '')
    ldap.connect()

    return _get(ldap, group)


def create(group, eonid, environment):
    """Create allocation group"""
    owner1 = os.getenv('USER')
    if owner1 == 'treadmlp':
        owner2 = 'treadmill-fwd-p'
    else:
        owner2 = 'treadmill-fwd-d'

    _madmin('NG', 'ID={},DESC="{}",ISC=I,REST=Y,MID={},MID={}'.format(
        group,
        _DESC,
        owner1,
        owner2
    ))
    _madmin('CA', 'ID={},ACL=YES'.format(group))
    _madmin('AE', 'ID={},EONID={}'.format(group, eonid))
    _madmin('AN', 'ID={},ENV={}'.format(group, environment.upper()))
    if environment != 'prod':
        _madmin('RN', 'ID={},ENV=PROD'.format(group))


def delete(group):
    """Delete allocation group"""
    _madmin('CA', 'ID={},ACL=NO'.format(group))
    _madmin('DG', 'ID={}'.format(group))


def insert(group, admins):
    """Add membership admins to group"""
    admins_p = ','.join(['MID=' + adm for adm in admins])
    _madmin('AS', 'ID={},{}'.format(group, admins_p))


def remove(group, admins):
    """Remove membership admins from group"""
    admins_p = ','.join(['MID=' + adm for adm in admins])
    _madmin('RS', 'ID={},{}'.format(group, admins_p))


def _get(ldap, group):
    """Get group details from fwd ldap"""
    entry = ldap.get('cn={},ou=Groups,o=Morgan Stanley'.format(group),
                     '(objectclass=msmailgroup)',
                     ['mseonid', 'msenvironment', 'msassistantacl',
                      'owner', 'cn'])

    group = {}
    group['name'] = entry['cn'][0]

    if 'mseonid' in entry:
        group['eonid'] = entry['mseonid'][0]
    else:
        group['eonid'] = None

    if 'msenvironment' in entry:
        group['environment'] = entry['msenvironment'][0].lower()
    else:
        group['environment'] = None

    group['owners'] = [_resolve_ldap_ref(ldap, owner)
                       for owner in entry['owner']]

    if 'msassistantacl' in entry:
        group['admins'] = [_resolve_ldap_ref(ldap, adm)
                           for adm in entry['msassistantacl']]
    else:
        group['admins'] = []

    return group


def _resolve_ldap_ref(ldap, ref):
    """Reolve ldap reference, and return name"""
    if ref.startswith('msfwid='):
        obj = ldap.get(ref, '(objectclass=msperson)', ['userid'])
        return obj['userid'][0]
    elif ref.startswith('cn='):
        cn = ref.split(',', 1)[0]
        return cn[3:]
    else:
        raise exc.TreadmillError('Unknown ldap ref: %s' % ref)


def _madmin(*args):
    """Run madmin with args"""
    command = [_MADMIN] + list(args)
    try:
        _LOGGER.debug('%s', ' '.join(command))
        subprocess.check_output(command)
    except subprocess.CalledProcessError as err:
        raise exc.TreadmillError(err.output.rstrip('\n'))
