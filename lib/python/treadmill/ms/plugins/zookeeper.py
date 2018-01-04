"""Zookeeper connection plugin.

Connect to Zookeeper with Kerberos authentication using proprietary
extension to kazoo.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import logging

import kazoo.zkutils
import kazoo


_LOGGER = logging.getLogger(__name__)

_WINDOWS_REALM_MAPPING = {
    'msad.ms.com': 'MSAD.MS.COM'
}


def connect(zkurl, connargs):
    """Return connected Zk client."""
    _LOGGER.debug('Kerberos connection to Zookeeper: %s', zkurl)
    zkproid, zkconnstr = zkurl[len('zookeeper://'):].split('@')
    if zkconnstr.find('/') != -1:
        zkconnstr = zkconnstr[:zkconnstr.find('/')]

    _LOGGER.debug('Proid: %s, connecting string: %s', zkproid, zkconnstr)
    return kazoo.zkutils.getKazooClient_connstring(
        zkconnstr,
        zkproid,
        **connargs
    )


def get_princ_realm(server):
    """Gets the princ and the realm for the given server.
    """
    partition = server.partition('.')
    name = partition[0]
    realm = partition[2].lower()
    if realm in _WINDOWS_REALM_MAPPING:
        name = '{0}$'.format(name.upper())
        realm = _WINDOWS_REALM_MAPPING[realm]
    else:
        name = 'host/{0}'.format(server.lower())
        realm = 'is1.morgan'

    return name, realm


def make_host_acl(host, perm):
    """Constructs a host based acl which differes on linux and windows.
    """
    name, _realm = get_princ_realm(host)
    return make_user_acl(name, perm)


def make_user_acl(user, perm):
    """Constructs an ACL based on user and permissions.

    ACL properties:
     - schema: kerberos
     - principal: user://<user>
    """
    return kazoo.security.make_acl('kerberos', 'user://%s' % user,
                                   read='r' in perm,
                                   write='w' in perm,
                                   create='c' in perm,
                                   delete='d' in perm,
                                   admin='a' in perm)


def make_role_acl(role, perm):
    """Constructs a file based acl based on role.

    Role file are assumed to be in /treadmill/roles directory.

    Treadmill master runs in chrooted environment, so path to roles files
    is hardcoded.
    """
    filename = '/'.join(['/treadmill/roles', role])
    return kazoo.security.make_acl(
        'kerberos', 'file://%s' % filename,
        read='r' in perm,
        write='w' in perm,
        create='c' in perm,
        delete='d' in perm,
        admin='a' in perm
    )
