"""Zookeeper connection plugin.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


def connect(zkurl, connargs):
    """Return connected Zk client."""
    del zkurl
    del connargs
    assert False


def make_user_acl(user, perm):
    """Constructs an ACL based on user and permissions.

    :param user:
        User name
    :type proto:
        ``str``
    :param perm:
        Permission string (i.e - 'rw', 'rwcda').
    :type proto:
        ``str``

    acl = kazoo.security.make_acl('<someschema>', 'user://%s' % user,
                                  read='r' in perm,
                                  write='w' in perm,
                                  create='c' in perm,
                                  delete='d' in perm,
                                  admin='a' in perm)
    return acl
    """
    del user
    del perm
    assert False


def make_role_acl(role, perm):
    """Constructs an acl based on role.

    :param role:
        Treadmill role - admin, reader, server
    :type proto:
        ``str``
    :param perm:
        Permission string (i.e - 'rw', 'rwcda').
    :type proto:
        ``str``

    acl = ...
    return acl
    """
    del role
    del perm
    assert False
