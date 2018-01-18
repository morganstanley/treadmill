"""Infra code exceptions.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals


class InfraBaseException(Exception):
    """Base exception for all infrastructure errors.
    """

    __slot__ = (
        'message',
    )

    def __init__(self, message):
        self.message = message


class LDAPNotFound(InfraBaseException):
    """When LDAP server is not provisioned.
    """

    def __init__(self):
        super(LDAPNotFound, self).__init__(
            'Please check if LDAP Server is up and running.'
        )


class IPAServerNotFound(InfraBaseException):
    """When IPA server is not provisioned.
    """

    def __init__(self):
        super(IPAServerNotFound, self).__init__(
            'Please check if IPA Server is up and running.'
        )
